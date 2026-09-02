from flask import g


ALL_MENU_ITEMS = [
    {"label": "Inicio", "icon": "home", "endpoint": "main.dashboard", "permission": None},
    {"label": "Productos", "icon": "inventory_2", "endpoint": "products.list", "permission": "products.view"},
    {"label": "Proveedores", "icon": "local_shipping", "endpoint": "suppliers.list", "permission": "suppliers.view"},
    {"label": "Compras", "icon": "shopping_cart", "endpoint": "purchases.list", "permission": "purchases.view"},
    {"label": "Clientes", "icon": "people", "endpoint": "customers.list", "permission": "customers.view"},
    {"label": "Ventas", "icon": "point_of_sale", "endpoint": "sales.list", "permission": "sales.view"},
    {"label": "Inventario", "icon": "warehouse", "endpoint": "inventory.stock", "permission": "inventory.view"},
    {"label": "Recursos Humanos", "icon": "groups", "endpoint": "hr.list", "permission": "hr.employees.view"},
    {"label": "Nomina", "icon": "payments", "endpoint": "payroll.index", "permission": "payroll.view"},
    {"label": "Reportes", "icon": "assessment", "endpoint": "reports.index", "permission": "reports.view"},
    {"label": "Administracion", "icon": "admin_panel_settings", "endpoint": "admin.users", "permission": "users.manage"},
]

ADMIN_SUBMENU = [
    {"label": "Usuarios", "icon": "people", "endpoint": "admin.users", "permission": "users.manage"},
    {"label": "Roles y permisos", "icon": "shield", "endpoint": "admin.roles", "permission": "roles.manage"},
    {"label": "Auditoria", "icon": "history", "endpoint": "admin.audit_log", "permission": "audit.view"},
]


def get_menu_items():
    user = g.user if hasattr(g, "user") else None
    if user is None:
        return []

    if user.role and user.role.name == "Administrador":
        items = []
        for item in ALL_MENU_ITEMS:
            if item["label"] == "Administracion":
                items.append({**item, "children": ADMIN_SUBMENU})
            else:
                items.append(item)
        return items

    allowed = []
    for item in ALL_MENU_ITEMS:
        if item["permission"] is None:
            allowed.append(item)
        elif user.has_permission(item["permission"]):
            allowed.append(item)
    return allowed
