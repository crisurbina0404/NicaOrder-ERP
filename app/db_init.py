from .extensions import db
from .models import User, Role, Permission, Department, Position
from .models.products import Category, Brand, Product
from .models.purchases import Supplier
from .models.customers import Customer
from .models.payroll import PayrollParameter, IncomeTaxBracket
from .models.hr import Employee, SalaryHistory


def init_db():
    db.create_all()
    _seed_initial_data()


def _seed_initial_data():
    if Role.query.first() is not None:
        return

    admin_role = Role(name="Administrador", description="Acceso total al sistema")
    vendedor_role = Role(name="Vendedor", description="Gestion de ventas y clientes")
    bodeguero_role = Role(name="Bodeguero", description="Control de inventario y almacen")
    rrhh_role = Role(name="RRHH", description="Recursos Humanos y gestion de personal")

    db.session.add_all([admin_role, vendedor_role, bodeguero_role, rrhh_role])
    db.session.flush()

    permissions = [
        Permission(name="users.manage", description="Gestionar usuarios", module="ADMIN"),
        Permission(name="roles.manage", description="Gestionar roles y permisos", module="ADMIN"),
        Permission(name="audit.view", description="Ver registros de auditoria", module="ADMIN"),
        Permission(name="config.manage", description="Configuracion general del sistema", module="ADMIN"),
        Permission(name="products.view", description="Consultar productos", module="PRODUCTS"),
        Permission(name="products.manage", description="Crear y editar productos", module="PRODUCTS"),
        Permission(name="suppliers.view", description="Consultar proveedores", module="SUPPLIERS"),
        Permission(name="suppliers.manage", description="Crear y editar proveedores", module="SUPPLIERS"),
        Permission(name="purchases.view", description="Consultar compras", module="PURCHASES"),
        Permission(name="purchases.manage", description="Crear y gestionar compras", module="PURCHASES"),
        Permission(name="purchases.receive", description="Recibir compras en almacen", module="PURCHASES"),
        Permission(name="customers.view", description="Consultar clientes", module="CUSTOMERS"),
        Permission(name="customers.manage", description="Crear y editar clientes", module="CUSTOMERS"),
        Permission(name="sales.view", description="Consultar ventas", module="SALES"),
        Permission(name="sales.manage", description="Crear y gestionar ventas", module="SALES"),
        Permission(name="sales.cancel", description="Cancelar ventas", module="SALES"),
        Permission(name="inventory.view", description="Consultar inventario", module="INVENTORY"),
        Permission(name="inventory.manage", description="Gestionar inventario", module="INVENTORY"),
        Permission(name="inventory.adjust", description="Ajustar inventario", module="INVENTORY"),
        Permission(name="reports.view", description="Ver reportes", module="REPORTS"),
        Permission(name="departments.manage", description="Gestionar departamentos", module="HR"),
        Permission(name="positions.manage", description="Gestionar cargos", module="HR"),
        Permission(name="hr.employees.view", description="Consultar empleados", module="HR"),
        Permission(name="hr.employees.manage", description="Crear y editar empleados", module="HR"),
        Permission(name="hr.salary.view", description="Consultar salarios", module="HR"),
        Permission(name="payroll.view", description="Consultar nomina", module="PAYROLL"),
        Permission(name="payroll.manage", description="Gestionar nomina y planillas", module="PAYROLL"),
        Permission(name="payroll.approve", description="Aprobar nomina", module="PAYROLL"),
    ]
    db.session.add_all(permissions)
    db.session.flush()

    perm_map = {p.name: p for p in permissions}
    admin_role.permissions = list(permissions)

    bodeguero_role.permissions = [
        perm_map["products.view"],
        perm_map["products.manage"],
        perm_map["suppliers.view"],
        perm_map["suppliers.manage"],
        perm_map["purchases.view"],
        perm_map["purchases.manage"],
        perm_map["purchases.receive"],
        perm_map["inventory.view"],
        perm_map["inventory.manage"],
        perm_map["inventory.adjust"],
    ]

    vendedor_role.permissions = [
        perm_map["products.view"],
        perm_map["customers.view"],
        perm_map["customers.manage"],
        perm_map["sales.view"],
        perm_map["sales.manage"],
        perm_map["inventory.view"],
    ]

    rrhh_role.permissions = [
        perm_map["hr.employees.view"],
        perm_map["hr.employees.manage"],
        perm_map["departments.manage"],
        perm_map["positions.manage"],
        perm_map["hr.salary.view"],
        perm_map["payroll.view"],
        perm_map["payroll.manage"],
    ]

    admin_user = User(
        username="admin",
        full_name="Administrador del Sistema",
        email="admin@nicaorder.local",
        role_id=admin_role.id,
        is_active=True,
        account_status="ACTIVA",
    )
    admin_user.set_password("test1234")

    db.session.add(admin_user)

    _seed_products()
    _seed_suppliers()
    _seed_customers()
    _seed_departments_positions()
    _seed_employees()
    _seed_payroll_data()
    db.session.commit()


def _seed_products():
    categories_data = [
        ("Proteccion Personal", "Articulos de proteccion individual"),
        ("Material de Curacion", "Insumos para curaciones y cuidado de heridas"),
        ("Desinfeccion", "Productos para desinfeccion y antisepsia"),
        ("Equipos Basicos", "Equipos de medicion y diagnostico basico"),
    ]
    categories = {}
    for name, desc in categories_data:
        cat = Category(name=name, description=desc)
        db.session.add(cat)
        db.session.flush()
        categories[name] = cat

    brands_data = [
        ("3M", "Empresa multinational de tecnologia y salud"),
        ("Medline", "Soluciones médicas y suministros"),
        ("Kleenex", "Productos de higiene y cuidado personal"),
        ("Omron", "Equipos electronicos de salud"),
        ("Adams", "Productos medicos genericos"),
    ]
    brands = {}
    for name, desc in brands_data:
        brand = Brand(name=name, description=desc)
        db.session.add(brand)
        db.session.flush()
        brands[name] = brand

    products_data = [
        {
            "code": "PP-001",
            "name": "Guantes Medicos Talla M",
            "description": "Guantes de latex sin polvo, talla media",
            "category": "Proteccion Personal",
            "brand": "Medline",
            "presentation": "Caja x 100 unidades",
            "unit": "Caja",
            "purchase_price": 12.50,
            "sale_price": 18.00,
            "minimum_stock": 50,
            "sanitary_registration": "RR-2024-001",
        },
        {
            "code": "PP-002",
            "name": "Mascarillas Quirurgicas",
            "description": "Mascarilla desechable de 3 capas",
            "category": "Proteccion Personal",
            "brand": "3M",
            "presentation": "Caja x 50 unidades",
            "unit": "Caja",
            "purchase_price": 8.00,
            "sale_price": 12.50,
            "minimum_stock": 100,
            "sanitary_registration": "RR-2024-002",
        },
        {
            "code": "DES-001",
            "name": "Alcohol Etilico 70%",
            "description": "Alcohol desinfectante para uso externo",
            "category": "Desinfeccion",
            "brand": "Kleenex",
            "presentation": "Frasco x 500ml",
            "unit": "Frasco",
            "purchase_price": 3.50,
            "sale_price": 6.00,
            "minimum_stock": 80,
            "sanitary_registration": "RR-2024-003",
        },
        {
            "code": "MC-001",
            "name": "Gasas Estériles 10x10",
            "description": "Gasas de algodon esterilizadas para curaciones",
            "category": "Material de Curacion",
            "brand": "Adams",
            "presentation": "Paquete x 10 unidades",
            "unit": "Paquete",
            "purchase_price": 2.00,
            "sale_price": 4.00,
            "minimum_stock": 150,
            "sanitary_registration": "RR-2024-004",
        },
        {
            "code": "MC-002",
            "name": "Jeringas 5ml sin aguja",
            "description": "Jeringa desechable de 5 mililitros",
            "category": "Material de Curacion",
            "brand": "Adams",
            "presentation": "Caja x 100 unidades",
            "unit": "Caja",
            "purchase_price": 10.00,
            "sale_price": 16.00,
            "minimum_stock": 60,
            "sanitary_registration": "RR-2024-005",
        },
        {
            "code": "EQ-001",
            "name": "Termometro Digital",
            "description": "Termometro digital de precision con flexible",
            "category": "Equipos Basicos",
            "brand": "Omron",
            "presentation": "Unidad",
            "unit": "Unidad",
            "purchase_price": 5.50,
            "sale_price": 10.00,
            "minimum_stock": 20,
            "sanitary_registration": "RR-2024-006",
        },
        {
            "code": "MC-003",
            "name": "Vendas Elasticas 10cm",
            "description": "Venda elastica adhesiva de 10 centimetros",
            "category": "Material de Curacion",
            "brand": "Adams",
            "presentation": "Unidad",
            "unit": "Unidad",
            "purchase_price": 1.80,
            "sale_price": 3.50,
            "minimum_stock": 100,
            "sanitary_registration": "RR-2024-007",
        },
        {
            "code": "EQ-002",
            "name": "Tensiometro Digital",
            "description": "Monitor de presion arterial de brazo automatico",
            "category": "Equipos Basicos",
            "brand": "Omron",
            "presentation": "Unidad",
            "unit": "Unidad",
            "purchase_price": 35.00,
            "sale_price": 55.00,
            "minimum_stock": 10,
            "sanitary_registration": "RR-2024-008",
        },
    ]

    for data in products_data:
        product = Product(
            code=data["code"],
            name=data["name"],
            description=data["description"],
            category_id=categories[data["category"]].id,
            brand_id=brands[data["brand"]].id,
            presentation=data["presentation"],
            unit=data["unit"],
            purchase_price=data["purchase_price"],
            sale_price=data["sale_price"],
            minimum_stock=data["minimum_stock"],
            sanitary_registration=data["sanitary_registration"],
            is_active=True,
        )
        db.session.add(product)


def _seed_suppliers():
    suppliers_data = [
        ("Distribuidora Medica S.A.", "J001001001", "2255-1001", "ventas@distmedica.com", "Managua, Km 6 Carretera Masaya", "Carlos Rodriguez"),
        ("Suministros Hospitalarios Nica", "J002002002", "2255-2002", "contacto@suminhosp.com", "Managua, Barrio Santiaguito", "Maria Lopez"),
        ("Importadora de Equipos Medicos", "J003003003", "2255-3003", "ventas@importmed.com", "Managua, Zona Industrial", "Pedro Martinez"),
        ("Proveedor General de Salud", "J004004004", "2255-4004", "info@progsalud.com", "Leon, Boulevard Simeon Rojas", "Ana Garcia"),
    ]

    for name, tax_id, phone, email, address, contact in suppliers_data:
        supplier = Supplier(
            name=name,
            tax_id=tax_id,
            phone=phone,
            email=email,
            address=address,
            contact_person=contact,
            is_active=True,
        )
        db.session.add(supplier)


def _seed_customers():
    customers_data = [
        ("Hospital Central de Managua", "J101001001", "2233-1001", "compras@hcmca.ni", "Managua, Km 4 Carretera Sur"),
        ("Clinica Santa Maria", "J202002002", "2233-2002", "admin@clinicasantamaria.ni", "Managua, Barrio Los Robles"),
        ("Laboratorio Clinico Norte", "J303003003", "2233-3003", "compras@labnorte.ni", "Esteli, Centro Comercial El Norte"),
        ("Centro Medico Bautista", "J404004004", "2233-4004", "adquisiciones@bautista.ni", "Leon, Av. Ortiz"),
        ("Farmacia Popular S.A.", "J505005005", "2233-5005", "compras@farmaciapopular.ni", "Masaya, Mercado Municipal"),
    ]

    for name, identity, phone, email, address in customers_data:
        customer = Customer(
            name=name,
            identity_number=identity,
            phone=phone,
            email=email,
            address=address,
            is_active=True,
        )
        db.session.add(customer)


def _seed_departments_positions():
    if Department.query.first() is not None:
        return

    departments_data = [
        ("Administracion", "Departamento de administracion general"),
        ("Ventas", "Departamento de ventas y atencion al cliente"),
        ("Bodega", "Departamento de almacen e inventario"),
        ("Contabilidad", "Departamento contable y financiero"),
        ("Recursos Humanos", "Gestion de talento humano"),
    ]
    departments = {}
    for name, desc in departments_data:
        dept = Department(name=name, description=desc, is_active=True)
        db.session.add(dept)
        db.session.flush()
        departments[name] = dept

    positions_data = [
        ("Gerente General", "Administracion", "Jefe de la operacion general"),
        ("Vendedor", "Ventas", "Atencion y venta a clientes"),
        ("Bodeguero", "Bodega", "Control de inventario y almacenes"),
        ("Contador", "Contabilidad", "Registro contable y financiero"),
        ("Auxiliar Administrativo", "Administracion", "Soporte administrativo"),
        ("Cajero", "Ventas", "Manejo de cobros y pagos"),
        ("Analista de RRHH", "Recursos Humanos", "Gestion de personal"),
    ]
    for name, dept_name, desc in positions_data:
        pos = Position(
            name=name,
            description=desc,
            is_active=True,
        )
        db.session.add(pos)


def _seed_employees():
    if Employee.query.first() is not None:
        return

    from datetime import date

    depts = {d.name: d.id for d in Department.query.all()}
    positions = {p.name: p.id for p in Position.query.all()}

    employees_data = [
        ("EMP-001", "Carlos", "Martinez", "001-120585-1001X", date(1985, 5, 12), "8888-1001", "carlos@nicaorder.com", "Managua, Barrio Martha Quezada", "Administracion", "Gerente General", date(2020, 3, 1), "INDEFINIDO", 35000.00),
        ("EMP-002", "Maria", "Lopez", "001-220390-1002X", date(1990, 3, 22), "8888-1002", "maria@nicaorder.com", "Managua, Villa Flor", "Ventas", "Vendedor", date(2021, 6, 15), "INDEFINIDO", 15000.00),
        ("EMP-003", "Pedro", "Rodriguez", "001-150788-1003X", date(1988, 7, 15), "8888-1003", "pedro@nicaorder.com", "Managua, Reparto San Jose", "Bodega", "Bodeguero", date(2022, 1, 10), "INDEFINIDO", 12000.00),
        ("EMP-004", "Ana", "Garcia", "001-300992-1004X", date(1992, 9, 30), "8888-1004", "ana@nicaorder.com", "Managua, Los Vanegas", "Contabilidad", "Contador", date(2021, 9, 1), "INDEFINIDO", 25000.00),
        ("EMP-005", "Luis", "Hernandez", "001-050495-1005X", date(1995, 4, 5), "8888-1005", "luis@nicaorder.com", "Managua, Bello Horizonte", "Ventas", "Cajero", date(2023, 2, 1), "INDEFINIDO", 10000.00),
        ("EMP-006", "Sofia", "Chavez", "001-180187-1006X", date(1987, 1, 18), "8888-1006", "sofia@nicaorder.com", "Managua, Quita Sueno", "Recursos Humanos", "Analista de RRHH", date(2022, 4, 1), "INDEFINIDO", 20000.00),
        ("EMP-007", "Roberto", "Morales", "001-250600-1007X", date(2000, 6, 25), "8888-1007", "roberto@nicaorder.com", "Managua, Jorge Dimitrov", "Administracion", "Auxiliar Administrativo", date(2024, 1, 15), "PLAZO_FIJO", 8000.00),
    ]

    for code, first, last, identity, birth, phone, email, address, dept_name, pos_name, hire, contract, salary in employees_data:
        emp = Employee(
            employee_code=code,
            first_name=first,
            last_name=last,
            identity_number=identity,
            birth_date=birth,
            phone=phone,
            email=email,
            address=address,
            department_id=depts[dept_name],
            position_id=positions[pos_name],
            hire_date=hire,
            contract_type=contract,
            base_salary=salary,
            status="ACTIVO",
        )
        db.session.add(emp)
        db.session.flush()

        sh = SalaryHistory(
            employee_id=emp.id,
            salary=salary,
            start_date=hire,
            end_date=None,
            reason="Salario inicial",
        )
        db.session.add(sh)


def _seed_payroll_data():
    if PayrollParameter.query.first() is not None:
        return

    parameters = [
        ("INSS_LABORAL", 7.0, "Tasa de aportacion del trabajador al INSS (7%)", None, None),
        ("INSS_PATRONAL", 12.25, "Tasa de aportacion del patrono al INSS (12.25%)", None, None),
        ("INATEC_LABORAL", 2.0, "Tasa de aportacion del trabajador al INATEC (2%)", None, None),
        ("INATEC_PATRONAL", 2.0, "Tasa de aportacion del patrono al INATEC (2%)", None, None),
        ("SALARIO_MINIMO", 356.86, "Salario minimo mensual", None, None),
        ("BONO_13_PORCENTAJE", 100.0, "Porcentaje del aguinaldo sobre salario mensual (1 vacacional)", None, None),
        ("VACACIONES_DIAS", 15, "Dias de vacaciones por anno trabajado", None, None),
        ("VACACIONES_PORCENTAJE", 100.0, "Porcentaje del salario para compensacion vacacional", None, None),
    ]

    for name, value, desc, start, end in parameters:
        param = PayrollParameter(
            name=name,
            value=value,
            description=desc,
            start_date=start,
            end_date=end,
            is_active=True,
        )
        db.session.add(param)

    brackets = [
        (0.00, 100000.00, 0.00, 0.0, 2025),
        (100000.01, 200000.00, 0.00, 15.0, 2025),
        (200000.01, 350000.00, 15000.00, 20.0, 2025),
        (350000.01, 500000.00, 45000.00, 25.0, 2025),
        (500000.01, None, 82500.00, 30.0, 2025),
        (0.00, 100000.00, 0.00, 0.0, 2026),
        (100000.01, 200000.00, 0.00, 15.0, 2026),
        (200000.01, 350000.00, 15000.00, 20.0, 2026),
        (350000.01, 500000.00, 45000.00, 25.0, 2026),
        (500000.01, None, 82500.00, 30.0, 2026),
    ]

    for lower, upper, base, pct, year in brackets:
        bracket = IncomeTaxBracket(
            lower_limit=lower,
            upper_limit=upper,
            base_tax=base,
            excess_percentage=pct,
            year=year,
            is_active=True,
        )
        db.session.add(bracket)
