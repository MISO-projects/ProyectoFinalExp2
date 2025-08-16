flowchart LR

  subgraph Personas
    cliente["Comprador Institucional"]
    fuerza["Representante de Ventas"]
    ops["Administrador de Operaciones"]
    gerente["Gerente Comercial"]
  end

  subgraph Sistema_Principal
    medisupply["Plataforma MediSupply<br/>(Web y Apps Móviles)"]
  end

  subgraph Sistemas_Externos
    erp["ERP / Contabilidad"]
    pagos["Pasarela de Pagos"]
    tms["Transportista / TMS"]
    proveedor["Proveedor"]
    notif["Servicio de Notificaciones"]
    maps["Geolocalización / Mapas"]
    bi["Plataforma BI / Analytics"]
    idp["Proveedor de Identidad (SSO)"]
  end


  cliente -->|Registra pedidos, consulta inventario y seguimiento| medisupply
  fuerza -->|Toma pedidos en campo, rutas/visitas, evidencias| medisupply
  ops -->|Compras, inventario, distribución, auditorías| medisupply
  gerente -->|Administra vendedores/planes y reportes KPI| medisupply


  medisupply -->|Sincroniza facturas, costos y CxC| erp
  erp -->|Estados de facturación y pagos| medisupply

  medisupply -->|Procesa pagos de pedidos| pagos
  pagos -->|Confirmaciones / conciliación| medisupply

  medisupply -->|Órdenes de despacho, ventanas y rutas| tms
  tms -->|Eventos de tracking y entregas| medisupply

  medisupply -->|Órdenes de compra y proyecciones| proveedor
  proveedor -->|Confirmaciones y notas de entrega| medisupply

  medisupply -->|Notificaciones transaccionales email/SMS/push| notif
  medisupply -->|Geocodificación, distancias y ruteo| maps
  medisupply -->|Exporta datasets de ventas, inventario y logística| bi
  medisupply -->|Inicio de sesión y SSO| idp

  class cliente,fuerza,ops,gerente actor;
  class medisupply sistema;
  class erp,pagos,tms,proveedor,notif,maps,bi,idp externo;
