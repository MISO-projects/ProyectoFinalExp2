from flask import Flask, request, jsonify
import numpy as np, time
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from traffic_manager import TrafficAPIManager

app = Flask(__name__)

def haversine_matrix(coords):
    R = 6371000.0
    lat = np.radians(np.array([c[0] for c in coords], dtype=np.float64))
    lon = np.radians(np.array([c[1] for c in coords], dtype=np.float64))
    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = np.sin(dlat/2.0)**2 + np.cos(lat)[:,None]*np.cos(lat)[None,:]*np.sin(dlon/2.0)**2
    return (2.0 * R * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))).astype(np.int64)

def solve_vrp(matrix, n_vehicles, time_limit_ms=4500):
    solve_start = time.perf_counter()
    print(f"Iniciando VRP: {matrix.shape[0]} puntos, {n_vehicles} vehículos, {time_limit_ms}ms límite")
    
    n = matrix.shape[0]
    manager = pywrapcp.RoutingIndexManager(n, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def dist_cb(f, t):
        i, j = manager.IndexToNode(f), manager.IndexToNode(t)
        return int(matrix[i, j])

    cb_index = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(cb_index)

    if n > n_vehicles and n_vehicles > 1:
        customers = n - 1
        max_capacity = max(1, (customers + n_vehicles - 1) // n_vehicles)
        
        def demand_cb(idx):
            return 1 if manager.IndexToNode(idx) != 0 else 0
        
        demand_cb_index = routing.RegisterUnaryTransitCallback(demand_cb)
        routing.AddDimensionWithVehicleCapacity(
            demand_cb_index, 0, [max_capacity] * n_vehicles, True, 'Capacity'
        )

    params = pywrapcp.DefaultRoutingSearchParameters()
    if n_vehicles > 1:
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    else:
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(time_limit_ms)
    params.log_search = False

    print(f"Configuración VRP: strategy={params.first_solution_strategy}, metaheuristic={params.local_search_metaheuristic}")
    
    sol = routing.SolveWithParameters(params)
    solve_time = (time.perf_counter() - solve_start) * 1000
    
    print(f"VRP resuelto en {solve_time:.0f}ms (límite: {time_limit_ms}ms)")
    
    routes = []
    total = 0
    if sol:
        print(f"Solución encontrada - Status: {routing.status()}")
        for v in range(n_vehicles):
            idx = routing.Start(v)
            path = []
            dist = 0
            customers_served = 0
            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                path.append(node)
                if node != 0:
                    customers_served += 1
                prev = idx
                idx = sol.Value(routing.NextVar(idx))
                dist += routing.GetArcCostForVehicle(prev, idx, v)
            path.append(manager.IndexToNode(idx))
            routes.append({
                "vehicle": v, 
                "stops": path, 
                "distance_m": dist,
                "customers_served": customers_served
            })
            total += dist
            if customers_served > 0:
                print(f"   Vehículo {v}: {customers_served} clientes, {dist}m")
    else:
        print(f"No se encontró solución - Status: {routing.status()}")
    
    result = {
        "routes": routes, 
        "total_distance_m": total, 
        "solution_found": sol is not None,
        "solver_info": {
            "actual_solve_time_ms": int(solve_time),
            "time_limit_used_ms": time_limit_ms,
            "solver_status": routing.status(),
            "time_limit_reached": solve_time >= time_limit_ms * 0.95
        }
    }
    
    if sol:
        active_vehicles = sum(1 for route in routes if len(route["stops"]) > 2)
        result["active_vehicles"] = active_vehicles
        result["vehicle_utilization"] = active_vehicles / n_vehicles
    
    return result

def solve_vrp_with_traffic(time_matrix: np.ndarray, n_vehicles: int, time_limit_ms: int = 4500):
    solve_start = time.perf_counter()
    print(f"Iniciando VRP con tráfico: {time_matrix.shape[0]} puntos, {n_vehicles} vehículos, {time_limit_ms}ms límite")
    
    n = time_matrix.shape[0]
    manager = pywrapcp.RoutingIndexManager(n, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_cb(f, t):
        i, j = manager.IndexToNode(f), manager.IndexToNode(t)
        return int(time_matrix[i, j])

    cb_index = routing.RegisterTransitCallback(time_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(cb_index)

    if n > n_vehicles and n_vehicles > 1:
        customers = n - 1
        max_capacity = max(1, (customers + n_vehicles - 1) // n_vehicles)
        
        def demand_cb(idx):
            return 1 if manager.IndexToNode(idx) != 0 else 0
        
        demand_cb_index = routing.RegisterUnaryTransitCallback(demand_cb)
        routing.AddDimensionWithVehicleCapacity(
            demand_cb_index, 0, [max_capacity] * n_vehicles, True, 'Capacity'
        )

    params = pywrapcp.DefaultRoutingSearchParameters()
    if n_vehicles > 1:
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    else:
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(time_limit_ms)
    params.log_search = False

    print(f"Configuración VRP-Traffic: strategy={params.first_solution_strategy}, metaheuristic={params.local_search_metaheuristic}")
    
    sol = routing.SolveWithParameters(params)
    solve_time = (time.perf_counter() - solve_start) * 1000
    
    print(f"VRP-Traffic resuelto en {solve_time:.0f}ms (límite: {time_limit_ms}ms)")
    
    routes = []
    total_time = 0
    
    if sol:
        print(f"Solución con tráfico encontrada - Status: {routing.status()}")
        for v in range(n_vehicles):
            idx = routing.Start(v)
            path = []
            route_time = 0
            customers_served = 0
            
            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                path.append(node)
                if node != 0:
                    customers_served += 1
                prev = idx
                idx = sol.Value(routing.NextVar(idx))
                route_time += routing.GetArcCostForVehicle(prev, idx, v)
            
            path.append(manager.IndexToNode(idx))
            routes.append({
                "vehicle": v, 
                "stops": path, 
                "travel_time_s": route_time,
                "travel_time_h": round(route_time / 3600, 2),
                "customers_served": customers_served
            })
            total_time += route_time
            if customers_served > 0:
                print(f"   Vehículo {v}: {customers_served} clientes, {route_time}s ({round(route_time/3600, 2)}h)")
    else:
        print(f"No se encontró solución con tráfico - Status: {routing.status()}")
    
    result = {
        "routes": routes, 
        "total_travel_time_s": total_time,
        "total_travel_time_h": round(total_time / 3600, 2),
        "solution_found": sol is not None,
        "solver_info": {
            "actual_solve_time_ms": int(solve_time),
            "time_limit_used_ms": time_limit_ms,
            "solver_status": routing.status(),
            "time_limit_reached": solve_time >= time_limit_ms * 0.95
        }
    }
    
    if sol:
        active_vehicles = sum(1 for route in routes if len(route["stops"]) > 2)
        result["active_vehicles"] = active_vehicles
        result["vehicle_utilization"] = active_vehicles / n_vehicles
    
    return result

def get_customer_assignments(routes):
    assignments = {}
    for route in routes:
        vehicle = route["vehicle"]
        for stop in route["stops"]:
            if stop != 0:
                assignments[stop] = vehicle
    return assignments

@app.post("/routes/plan")
def plan():
    t0 = time.perf_counter()
    data = request.get_json(force=True)

    vehicles = int(data.get("vehicles", 1))
    points = data.get("points", [])
    tl_ms = int(data.get("time_limit_ms", 3500))
    
    print(f"DEBUG: Recibidos {len(points)} puntos originales")
    
    if not (1 <= vehicles <= 20):
        return jsonify({"error": "vehicles must be 1..20"}), 400
    if not (3 <= len(points) <= 150):
        return jsonify({"error": "points must be 3..150"}), 400

    # Filtrar puntos con coordenadas válidas
    valid_coords = []
    invalid_count = 0
    for i, p in enumerate(points):
        if p.get("lat") is not None and p.get("lng") is not None:
            try:
                lat = float(p["lat"])
                lng = float(p["lng"])
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    valid_coords.append((lat, lng))
                else:
                    print(f"DEBUG: Punto {i} con coordenadas inválidas: lat={lat}, lng={lng}")
                    invalid_count += 1
            except (ValueError, TypeError):
                print(f"DEBUG: Punto {i} con coordenadas no numéricas: lat={p.get('lat')}, lng={p.get('lng')}")
                invalid_count += 1
        else:
            print(f"DEBUG: Punto {i} con coordenadas faltantes: lat={p.get('lat')}, lng={p.get('lng')}")
            invalid_count += 1
    
    coords = valid_coords
    if invalid_count > 0:
        print(f"DEBUG: Se filtraron {invalid_count} puntos inválidos. Puntos válidos: {len(coords)}")
    t1 = time.perf_counter()
    M = haversine_matrix(coords)
    t2 = time.perf_counter()
    res = solve_vrp(M, vehicles, time_limit_ms=tl_ms)
    t3 = time.perf_counter()

    out = {
        "solution": res,
        "metrics": {
            "validate_ms": int((t1 - t0)*1000),
            "matrix_ms": int((t2 - t1)*1000),
            "solve_ms": int((t3 - t2)*1000),
            "duration_ms": int((t3 - t0)*1000)
        }
    }
    return jsonify(out), 200

@app.post("/routes/plan-with-osmr")
def plan_with_osmr():
    t0 = time.perf_counter()
    data = request.get_json(force=True)

    vehicles = int(data.get("vehicles", 1))
    points = data.get("points", [])
    tl_ms = int(data.get("time_limit_ms", 4500))
    departure_time = data.get("departure_time", "now")
    
    print(f"DEBUG: Recibidos {len(points)} puntos originales")
    
    if not (1 <= vehicles <= 20):
        return jsonify({"error": "vehicles must be 1..20"}), 400
    if not (3 <= len(points) <= 150):
        return jsonify({"error": "points must be 3..150 for traffic-aware routing"}), 400

    # Filtrar puntos con coordenadas válidas
    valid_coords = []
    invalid_count = 0
    for i, p in enumerate(points):
        if p.get("lat") is not None and p.get("lng") is not None:
            try:
                lat = float(p["lat"])
                lng = float(p["lng"])
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    valid_coords.append((lat, lng))
                else:
                    print(f"DEBUG: Punto {i} con coordenadas inválidas: lat={lat}, lng={lng}")
                    invalid_count += 1
            except (ValueError, TypeError):
                print(f"DEBUG: Punto {i} con coordenadas no numéricas: lat={p.get('lat')}, lng={p.get('lng')}")
                invalid_count += 1
        else:
            print(f"DEBUG: Punto {i} con coordenadas faltantes: lat={p.get('lat')}, lng={p.get('lng')}")
            invalid_count += 1
    
    coords = valid_coords
    if invalid_count > 0:
        print(f"DEBUG: Se filtraron {invalid_count} puntos inválidos. Puntos válidos: {len(coords)}")
    t1 = time.perf_counter()
    
    try:
        traffic_manager = TrafficAPIManager()
        traffic_result = traffic_manager.calculate_traffic_matrix(coords)
        time_matrix = traffic_result['matrix']
    except Exception as e:
        return jsonify({"error": f"OSRM API error: {str(e)}"}), 500
    
    t2 = time.perf_counter()
    
    vrp_result = solve_vrp_with_traffic(time_matrix, vehicles, time_limit_ms=tl_ms)
    t3 = time.perf_counter()

    out = {
        "solution": vrp_result,
        "traffic_info": {
            "provider": traffic_result['provider_used'],
            "has_realtime_traffic": traffic_result['has_realtime_traffic'],
            "departure_time": departure_time,
            "matrix_calculation_ms": traffic_result['calculation_time_ms']
        },
        "metrics": {
            "validate_ms": int((t1 - t0) * 1000),
            "traffic_matrix_ms": int((t2 - t1) * 1000),
            "solve_ms": int((t3 - t2) * 1000),
            "duration_ms": int((t3 - t0) * 1000)
        }
    }
    
    return jsonify(out), 200

@app.post("/debug/compare-haversine-vs-osrm")
def compare_haversine_vs_osrm():
    data = request.get_json(force=True)
    vehicles = int(data.get("vehicles", 3))
    points = data.get("points", [])
    time_limits = data.get("time_limits", [1000, 3000, 5000, 10000, 20000])
    avg_speed_kmh = float(data.get("avg_speed_kmh", 50))
    
    if not (3 <= len(points) <= 150):
        return jsonify({"error": "points must be 3..25 for OSRM comparison"}), 400
    
    coords = [(p["lat"], p["lng"]) for p in points]
    
    print(f"\nCOMPARACION HAVERSINE vs OSRM: {len(points)} puntos, {vehicles} vehículos")
    
    haversine_results = []
    osrm_results = []
    
    print(f"\nPROBANDO CON HAVERSINE:")
    for time_limit in time_limits:
        try:
            M = haversine_matrix(coords)
            result = solve_vrp(M, vehicles, time_limit_ms=time_limit)
            distance_m = result.get("total_distance_m", 0)
            estimated_time_s = (distance_m / 1000) / avg_speed_kmh * 3600
            
            haversine_results.append({
                "time_limit_ms": time_limit,
                "total_distance_m": distance_m,
                "estimated_time_s": int(estimated_time_s),
                "solve_time_ms": result.get("solver_info", {}).get("actual_solve_time_ms", 0),
                "method": "haversine",
                "solution": result
            })
            print(f"   {time_limit:>5}ms → {distance_m:>8}m (~{int(estimated_time_s):>6}s)")
            print(f"      Debug: {len(result.get('routes', []))} rutas, solution_found: {result.get('solution_found', False)}")
            print(f"      Keys en result: {list(result.keys())}")
            if 'routes' in result and result['routes']:
                print(f"      Primera ruta: vehículo {result['routes'][0].get('vehicle')}, clientes: {result['routes'][0].get('customers_served')}")
        except Exception as e:
            haversine_results.append({"time_limit_ms": time_limit, "error": str(e), "method": "haversine"})
    
    print(f"\nPROBANDO CON OSRM:")
    for time_limit in time_limits:
        try:
            traffic_manager = TrafficAPIManager()
            traffic_result = traffic_manager.calculate_traffic_matrix(coords)
            time_matrix = traffic_result['matrix']
            result = solve_vrp_with_traffic(time_matrix, vehicles, time_limit_ms=time_limit)
            actual_time_s = result.get("total_travel_time_s", 0)
            estimated_distance_m = int((actual_time_s / 3600) * avg_speed_kmh * 1000)
            
            osrm_results.append({
                "time_limit_ms": time_limit,
                "total_time_s": actual_time_s,
                "estimated_distance_m": estimated_distance_m,
                "solve_time_ms": result.get("solver_info", {}).get("actual_solve_time_ms", 0),
                "method": "osrm",
                "solution": result  
            })
            print(f"   {time_limit:>5}ms → {actual_time_s:>8}s (~{estimated_distance_m:>6}m)")
            print(f"      Debug: {len(result.get('routes', []))} rutas, solution_found: {result.get('solution_found', False)}")
            print(f"      Keys en result: {list(result.keys())}")
            if 'routes' in result and result['routes']:
                print(f"      Primera ruta: vehículo {result['routes'][0].get('vehicle')}, clientes: {result['routes'][0].get('customers_served')}")
        except Exception as e:
            osrm_results.append({"time_limit_ms": time_limit, "error": str(e), "method": "osrm"})
    
    def calculate_percentage_improvements(results, metric_key):
        improvements = []
        for i in range(1, len(results)):
            if "error" not in results[i] and "error" not in results[i-1]:
                prev_value = results[i-1][metric_key]
                curr_value = results[i][metric_key]
                improvement_pct = ((prev_value - curr_value) / prev_value) * 100 if prev_value > 0 else 0
                
                improvements.append({
                    "from_ms": results[i-1]["time_limit_ms"],
                    "to_ms": results[i]["time_limit_ms"],
                    "improvement_pct": round(improvement_pct, 3)
                })
        return improvements
    
    haversine_improvements = calculate_percentage_improvements(haversine_results, "estimated_time_s")
    osrm_improvements = calculate_percentage_improvements(osrm_results, "total_time_s")
    
    print(f"\nCOMPARACION DE PATRONES DE MEJORA:")
    print(f"\nHAVERSINE (mejoras porcentuales):")
    for imp in haversine_improvements:
        status = "[HIGH]" if imp["improvement_pct"] > 1 else "[GOOD]" if imp["improvement_pct"] > 0.1 else "[MINOR]" if imp["improvement_pct"] > 0 else "[NONE]"
        print(f"   {status} {imp['from_ms']:>5}ms→{imp['to_ms']:>5}ms: {imp['improvement_pct']:>6.3f}%")
    
    print(f"\nOSRM (mejoras porcentuales):")
    for imp in osrm_improvements:
        status = "[HIGH]" if imp["improvement_pct"] > 1 else "[GOOD]" if imp["improvement_pct"] > 0.1 else "[MINOR]" if imp["improvement_pct"] > 0 else "[NONE]"
        print(f"   {status} {imp['from_ms']:>5}ms→{imp['to_ms']:>5}ms: {imp['improvement_pct']:>6.3f}%")
    
    pattern_similarity = 0
    if len(haversine_improvements) == len(osrm_improvements):
        differences = [abs(h["improvement_pct"] - o["improvement_pct"]) 
                      for h, o in zip(haversine_improvements, osrm_improvements)]
        avg_difference = sum(differences) / len(differences) if differences else 0
        pattern_similarity = max(0, 100 - avg_difference * 10)
    
    print(f"\nSIMILITUD DE PATRONES: {pattern_similarity:.1f}%")
    
    route_comparisons = []
    for i, time_limit in enumerate(time_limits):
        if i < len(haversine_results) and i < len(osrm_results):
            h_result = haversine_results[i]
            o_result = osrm_results[i]
            
            if "error" not in h_result and "error" not in o_result:
                h_routes = []
                o_routes = []
                
                h_solution = h_result.get("solution", {})
                if "routes" in h_solution:
                    for route in h_solution["routes"]:
                        if route.get("customers_served", 0) > 0:
                            h_routes.append({
                                "vehicle": route["vehicle"],
                                "stops": route["stops"],
                                "customers": route["customers_served"]
                            })
                
                o_solution = o_result.get("solution", {})
                if "routes" in o_solution:
                    for route in o_solution["routes"]:
                        if route.get("customers_served", 0) > 0:
                            o_routes.append({
                                "vehicle": route["vehicle"], 
                                "stops": route["stops"],
                                "customers": route["customers_served"]
                            })
                
                print(f"      Rutas extraídas - Haversine: {len(h_routes)}, OSRM: {len(o_routes)}")
                
                route_similarity = calculate_route_similarity(h_routes, o_routes)
                
                route_comparisons.append({
                    "time_limit_ms": time_limit,
                    "haversine_routes": h_routes,
                    "osrm_routes": o_routes,
                    "route_similarity_pct": route_similarity,
                    "identical_routes": route_similarity > 95,
                    "similar_assignments": route_similarity > 70,
                    "route_analysis": analyze_route_differences(h_routes, o_routes)
                })
    
    avg_route_similarity = sum(rc.get("route_similarity_pct", 0) for rc in route_comparisons) / len(route_comparisons) if route_comparisons else 0
    
    print(f"\nANALISIS DE RUTAS:")
    for rc in route_comparisons:
        status = "[HIGH]" if rc["route_similarity_pct"] > 90 else "[MED]" if rc["route_similarity_pct"] > 70 else "[LOW]"
        print(f"   {status} {rc['time_limit_ms']:>5}ms: {rc['route_similarity_pct']:>5.1f}% similitud de rutas")
        
        if rc["route_similarity_pct"] < 90:
            analysis = rc["route_analysis"]
            if analysis["different_assignments"] > 0:
                print(f"      → {analysis['different_assignments']} asignaciones diferentes")
            if analysis["route_order_differences"] > 0:
                print(f"      → {analysis['route_order_differences']} órdenes de visita diferentes")
    
    print(f"\nSIMILITUD PROMEDIO DE RUTAS: {avg_route_similarity:.1f}%")
    
    return jsonify({
        "haversine_results": haversine_results,
        "osrm_results": osrm_results,
        "percentage_improvements": {
            "haversine": haversine_improvements,
            "osrm": osrm_improvements
        },
        "route_analysis": {
            "detailed_comparisons": route_comparisons,
            "avg_route_similarity_pct": round(avg_route_similarity, 1),
            "interpretation": {
                "identical_routing": avg_route_similarity > 95,
                "similar_routing": avg_route_similarity > 80,
                "different_routing": avg_route_similarity < 70,
                "explanation": "Alta similitud indica que ambos métodos toman decisiones de enrutamiento muy similares"
            }
        },
        "pattern_analysis": {
            "avg_speed_used_kmh": avg_speed_kmh,
            "pattern_similarity_pct": round(pattern_similarity, 1),
            "interpretation": {
                "high_similarity": pattern_similarity > 80,
                "similar_behavior": pattern_similarity > 60,
                "explanation": "Similitud alta indica que ambos métodos siguen patrones similares de optimización"
            }
        },
        "overall_comparison": {
            "performance_pattern_similarity": round(pattern_similarity, 1),
            "routing_decision_similarity": round(avg_route_similarity, 1),
            "haversine_pattern": "convergencia_subita" if any(imp["improvement_pct"] > 2 for imp in haversine_improvements) else "rendimientos_decrecientes",
            "osrm_pattern": "convergencia_subita" if any(imp["improvement_pct"] > 2 for imp in osrm_improvements) else "rendimientos_decrecientes",
            "overall_conclusion": determine_overall_conclusion(pattern_similarity, avg_route_similarity)
        }
    }), 200

def calculate_route_similarity(routes1, routes2):
    if not routes1 or not routes2:
        return 0.0
    
    assignments1 = get_customer_assignments(routes1)
    assignments2 = get_customer_assignments(routes2)
    
    if not assignments1 or not assignments2:
        return 0.0
    
    total_customers = len(set(assignments1.keys()) | set(assignments2.keys()))
    if total_customers == 0:
        return 100.0
    
    identical_assignments = 0
    for customer in assignments1:
        if customer in assignments2 and assignments1[customer] == assignments2[customer]:
            identical_assignments += 1
    
    route_order_similarity = 0
    total_routes = max(len(routes1), len(routes2))
    
    for route1 in routes1:
        best_match = 0
        for route2 in routes2:
            stops1 = [s for s in route1["stops"] if s != 0]
            stops2 = [s for s in route2["stops"] if s != 0]
            
            if set(stops1) == set(stops2):
                if stops1 == stops2:
                    best_match = 1.0
                else:
                    best_match = 0.7
                break
        route_order_similarity += best_match
    
    assignment_similarity = (identical_assignments / total_customers) * 100
    order_similarity = (route_order_similarity / total_routes) * 100 if total_routes > 0 else 0
    
    return (assignment_similarity * 0.7) + (order_similarity * 0.3)

def analyze_route_differences(routes1, routes2):
    assignments1 = get_customer_assignments(routes1)
    assignments2 = get_customer_assignments(routes2)
    
    different_assignments = 0
    route_order_differences = 0
    
    for customer in assignments1:
        if customer in assignments2 and assignments1[customer] != assignments2[customer]:
            different_assignments += 1
    
    for route1 in routes1:
        for route2 in routes2:
            if route1["vehicle"] == route2["vehicle"]:
                stops1 = [s for s in route1["stops"] if s != 0]
                stops2 = [s for s in route2["stops"] if s != 0]
                if set(stops1) == set(stops2) and stops1 != stops2:
                    route_order_differences += 1
    
    return {
        "different_assignments": different_assignments,
        "route_order_differences": route_order_differences,
        "total_customers": len(assignments1)
    }

def determine_overall_conclusion(pattern_similarity, route_similarity):
    if pattern_similarity > 85 and route_similarity > 90:
        return "MÉTODOS VIRTUALMENTE IDÉNTICOS: Mismas rutas y mismo comportamiento de optimización"
    elif pattern_similarity > 80 and route_similarity > 80:
        return "MÉTODOS MUY SIMILARES: Comportamiento y rutas muy parecidos con diferencias menores"
    elif pattern_similarity > 70 or route_similarity > 70:
        return "MÉTODOS SIMILARES: Algunos patrones comunes pero con diferencias notables en rutas"
    else:
        return "MÉTODOS DIFERENTES: Comportamientos y decisiones de enrutamiento significativamente distintos"



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
