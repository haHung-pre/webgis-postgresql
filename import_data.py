"""
Script import dữ liệu Shapefile vào PostgreSQL/PostGIS
Chạy bằng Python nếu không có shp2pgsql:
    python import_data.py
"""
import psycopg2
import geopandas as gpd
import os

# ============================================================
# CẤU HÌNH - Sửa thông tin kết nối và đường dẫn shapefile
# ============================================================
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'quanghung_gis',
    'user': 'postgres',
    'password': '123456'  # Đổi thành password của bạn
}

# Thư mục chứa file shapefile (thư mục includes)
SHAPEFILE_DIR = r'C:\path\to\Garbage\includes'  # SỬA ĐƯỜNG DẪN NÀY

LAYERS = {
    'garbage': ('garbadge.shp', 'Point'),
    'road':    ('road.shp', 'LineString'),
    'building':('building.shp', 'Polygon'),
    'bounds':  ('bounds.shp', 'Polygon'),
}

SOURCE_CRS = 'EPSG:32648'  # UTM Zone 48N

def import_layer(conn, name, filename, geom_type):
    """Import một layer shapefile vào PostgreSQL"""
    filepath = os.path.join(SHAPEFILE_DIR, filename)
    print(f"  Đọc {filename}...")
    
    gdf = gpd.read_file(filepath)
    gdf = gdf.set_crs(SOURCE_CRS, allow_override=True)
    
    cur = conn.cursor()
    
    # Drop table nếu đã tồn tại
    cur.execute(f'DROP TABLE IF EXISTS {name} CASCADE')
    
    # Tạo table với các cột
    cols = []
    for col in gdf.columns:
        if col == 'geometry':
            continue
        dtype = str(gdf[col].dtype)
        if 'int' in dtype:
            cols.append(f'"{col}" INTEGER')
        elif 'float' in dtype:
            cols.append(f'"{col}" FLOAT')
        else:
            cols.append(f'"{col}" TEXT')
    
    cols_str = ', '.join(cols)
    if cols_str:
        cur.execute(f'''
            CREATE TABLE {name} (
                gid SERIAL PRIMARY KEY,
                {cols_str},
                geom GEOMETRY({geom_type}, 32648)
            )
        ''')
    else:
        cur.execute(f'''
            CREATE TABLE {name} (
                gid SERIAL PRIMARY KEY,
                geom GEOMETRY({geom_type}, 32648)
            )
        ''')
    
    # Insert rows
    count = 0
    for _, row in gdf.iterrows():
        non_geom_cols = [c for c in gdf.columns if c != 'geometry']
        if non_geom_cols:
            col_names = ', '.join(f'"{c}"' for c in non_geom_cols) + ', geom'
            placeholders = ', '.join(['%s'] * len(non_geom_cols)) + ', ST_SetSRID(ST_GeomFromText(%s), 32648)'
            values = [str(row[c]) if row[c] is not None else None for c in non_geom_cols]
            values.append(row['geometry'].wkt)
        else:
            col_names = 'geom'
            placeholders = 'ST_SetSRID(ST_GeomFromText(%s), 32648)'
            values = [row['geometry'].wkt]
        
        cur.execute(f'INSERT INTO {name} ({col_names}) VALUES ({placeholders})', values)
        count += 1
    
    # Spatial index
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{name}_geom ON {name} USING GIST(geom)')
    
    conn.commit()
    print(f"  ✅ {name}: {count} features imported")

def main():
    print("=" * 50)
    print("Import dữ liệu GIS - Bãi rác Quang Hưng")
    print("=" * 50)
    
    conn = psycopg2.connect(**DB_CONFIG)
    
    # Setup PostGIS
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    conn.commit()
    print("✅ PostGIS extension sẵn sàng\n")
    
    # Import từng layer
    for name, (filename, geom_type) in LAYERS.items():
        print(f"📦 Import layer: {name}")
        import_layer(conn, name, filename, geom_type)
    
    # Post-processing
    cur = conn.cursor()
    cur.execute("ALTER TABLE garbage ADD COLUMN IF NOT EXISTS name TEXT DEFAULT 'Bãi rác'")
    cur.execute("ALTER TABLE garbage ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Công nghiệp'")
    cur.execute("ALTER TABLE building ADD COLUMN IF NOT EXISTS area_m2 FLOAT")
    cur.execute("UPDATE building SET area_m2 = ST_Area(geom)")
    conn.commit()
    
    print("\n✅ Import hoàn tất!")
    print("Chạy ứng dụng: python app.py")
    conn.close()

if __name__ == '__main__':
    main()
