"""
Script import tất cả 5 Shapefile vào PostgreSQL/PostGIS
Chạy: python import_data.py
"""
import psycopg2, geopandas as gpd, os

DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'database': 'quanghung_gis',
    'user': 'postgres',
    'password': '123456'   # ← SỬA password
}

# Đường dẫn đến thư mục chứa file .shp (thư mục includes/)
SHAPEFILE_DIR = r'C:\path\to\Garbage\includes'  # ← SỬA đường dẫn

LAYERS = {
    # tên_bảng : (file.shp, loại geometry, ghi chú)
    'garbage'    : ('garbadge.shp',             'Point',      True),
    'road'       : ('road.shp',                 'LineString', True),
    'building'   : ('building.shp',             'Polygon',    True),
    'bounds'     : ('bounds.shp',               'Polygon',    True),
    'path_graph' : ('instruction-generated.shp','LineString', True),
}

SOURCE_CRS = 'EPSG:32648'

def import_layer(conn, table, filename, geom_type):
    fp = os.path.join(SHAPEFILE_DIR, filename)
    print(f"  Đọc {filename}...")
    gdf = gpd.read_file(fp).set_crs(SOURCE_CRS, allow_override=True)
    cur = conn.cursor()
    cur.execute(f'DROP TABLE IF EXISTS {table} CASCADE')

    # Xây cột từ dataframe
    col_defs = []
    for col in gdf.columns:
        if col == 'geometry': continue
        dt = str(gdf[col].dtype)
        col_defs.append(f'"{col}" {"INTEGER" if "int" in dt else "FLOAT" if "float" in dt else "TEXT"}')

    cols_str = (', '.join(col_defs)+', ' if col_defs else '')
    cur.execute(f"""
        CREATE TABLE {table} (
            gid SERIAL PRIMARY KEY,
            {cols_str}geom GEOMETRY({geom_type}, 32648)
        )
    """)

    for _, row in gdf.iterrows():
        nc = [c for c in gdf.columns if c != 'geometry']
        if nc:
            names = ', '.join(f'"{c}"' for c in nc) + ', geom'
            phs   = ', '.join(['%s']*len(nc)) + ', ST_SetSRID(ST_GeomFromText(%s),32648)'
            vals  = [str(row[c]) if row[c] is not None else None for c in nc] + [row.geometry.wkt]
        else:
            names = 'geom'
            phs   = 'ST_SetSRID(ST_GeomFromText(%s),32648)'
            vals  = [row.geometry.wkt]
        cur.execute(f'INSERT INTO {table}({names}) VALUES({phs})', vals)

    cur.execute(f'CREATE INDEX idx_{table}_geom ON {table} USING GIST(geom)')
    conn.commit()
    print(f"  ✅ {table}: {len(gdf)} features")

def main():
    print("="*55)
    print("  Import GIS – Bãi rác KCN Quang Hưng")
    print("="*55)
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    conn.commit()
    print("✅ PostGIS OK\n")

    for table, (fn, gt, _) in LAYERS.items():
        print(f"📦 Layer: {table}")
        import_layer(conn, table, fn, gt)

    # Post-processing
    cur = conn.cursor()
    stmts = [
        "ALTER TABLE garbage    ADD COLUMN IF NOT EXISTS name     TEXT DEFAULT 'Bãi rác'",
        "ALTER TABLE garbage    ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Công nghiệp'",
        "UPDATE garbage SET name = 'Bãi rác ' || gid WHERE name = 'Bãi rác'",
        "ALTER TABLE building   ADD COLUMN IF NOT EXISTS area_m2  FLOAT",
        "ALTER TABLE building   ADD COLUMN IF NOT EXISTS perim_m  FLOAT",
        "UPDATE building SET area_m2 = ST_Area(geom), perim_m = ST_Perimeter(geom)",
        "ALTER TABLE road       ADD COLUMN IF NOT EXISTS length_m FLOAT",
        "UPDATE road SET length_m = ST_Length(geom)",
        "ALTER TABLE path_graph ADD COLUMN IF NOT EXISTS length_m FLOAT",
        "UPDATE path_graph SET length_m = ST_Length(geom)",
    ]
    for s in stmts:
        cur.execute(s)
    conn.commit()

    print("\n✅ Import hoàn tất! Chạy: python app.py")
    conn.close()

if __name__ == '__main__':
    main()
