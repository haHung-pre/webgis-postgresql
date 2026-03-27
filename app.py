"""
Ứng dụng web GIS - Bãi rác Khu công nghiệp Quang Hưng
Flask + PostGIS + Leaflet.js
"""
from flask import Flask, jsonify, render_template, request
import psycopg2
import psycopg2.extras
import json
import os

app = Flask(__name__)

# ============================================================
# CẤU HÌNH DATABASE - Sửa thông tin kết nối tại đây
# ============================================================
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'quanghung_gis',
    'user': 'postgres',
    'password': '123456'  # Đổi thành password PostgreSQL của bạn
}

def get_db():
    """Tạo kết nối đến PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Lỗi kết nối DB: {e}")
        return None

# ============================================================
# ROUTES - Trang web
# ============================================================

@app.route('/')
def index():
    """Trang chủ - bản đồ Leaflet"""
    return render_template('index.html')

# ============================================================
# API - Trả về dữ liệu GeoJSON cho bản đồ
# ============================================================

@app.route('/api/garbage')
def api_garbage():
    """API lấy dữ liệu bãi rác (GeoJSON)"""
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Không thể kết nối database'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(feat), '[]'::json)
            ) AS geojson
            FROM (
                SELECT json_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(ST_Transform(geom, 4326))::json,
                    'properties', json_build_object(
                        'id', gid,
                        'name', COALESCE(name, 'Bãi rác ' || gid),
                        'category', COALESCE(category, 'Công nghiệp'),
                        'lon', ST_X(ST_Transform(geom, 4326)),
                        'lat', ST_Y(ST_Transform(geom, 4326))
                    )
                ) AS feat
                FROM garbage
            ) features;
        """)
        result = cur.fetchone()
        return jsonify(result['geojson'])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/road')
def api_road():
    """API lấy dữ liệu đường đi (GeoJSON)"""
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Không thể kết nối database'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(feat), '[]'::json)
            ) AS geojson
            FROM (
                SELECT json_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(ST_Transform(geom, 4326))::json,
                    'properties', json_build_object(
                        'id', gid,
                        'nb_lanes', "nbLanes"
                    )
                ) AS feat
                FROM road
            ) features;
        """)
        result = cur.fetchone()
        return jsonify(result['geojson'])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/building')
def api_building():
    """API lấy dữ liệu tòa nhà (GeoJSON)"""
    nature = request.args.get('nature', None)
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Không thể kết nối database'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where_clause = "WHERE \"NATURE\" = %(nature)s" if nature else ""
        cur.execute(f"""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(feat), '[]'::json)
            ) AS geojson
            FROM (
                SELECT json_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(ST_Transform(geom, 4326))::json,
                    'properties', json_build_object(
                        'id', gid,
                        'nature', "NATURE",
                        'company', "COMPANY",
                        'area_m2', ROUND(area_m2::numeric, 1)
                    )
                ) AS feat
                FROM building
                {where_clause}
            ) features;
        """, {'nature': nature})
        result = cur.fetchone()
        return jsonify(result['geojson'])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/bounds')
def api_bounds():
    """API lấy ranh giới khu vực (GeoJSON)"""
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Không thể kết nối database'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(feat), '[]'::json)
            ) AS geojson
            FROM (
                SELECT json_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(ST_Transform(geom, 4326))::json,
                    'properties', json_build_object('id', gid)
                ) AS feat
                FROM bounds
            ) features;
        """)
        result = cur.fetchone()
        return jsonify(result['geojson'])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# ============================================================
# API - Truy vấn không gian
# ============================================================

@app.route('/api/query/nearby-buildings')
def query_nearby_buildings():
    """Tìm tòa nhà gần bãi rác trong bán kính r mét"""
    radius = request.args.get('radius', 200, type=int)
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Không thể kết nối database'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT DISTINCT
                b.gid,
                b."NATURE"  AS nature,
                b."COMPANY" AS company,
                ROUND(b.area_m2::numeric, 1) AS area_m2,
                ROUND(MIN(ST_Distance(b.geom, g.geom))::numeric, 1) AS min_distance_m,
                ST_AsGeoJSON(ST_Transform(b.geom, 4326))::json AS geometry
            FROM building b
            JOIN garbage g ON ST_DWithin(b.geom, g.geom, %(radius)s)
            GROUP BY b.gid, b."NATURE", b."COMPANY", b.area_m2, b.geom
            ORDER BY min_distance_m ASC
        """, {'radius': radius})
        rows = cur.fetchall()
        
        features = []
        for row in rows:
            features.append({
                'type': 'Feature',
                'geometry': row['geometry'],
                'properties': {
                    'id': row['gid'],
                    'nature': row['nature'],
                    'company': row['company'],
                    'area_m2': row['area_m2'],
                    'min_distance_m': row['min_distance_m']
                }
            })
        
        return jsonify({
            'type': 'FeatureCollection',
            'features': features,
            'query_info': {
                'radius_m': radius,
                'total_buildings': len(features)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/query/stats')
def query_stats():
    """Thống kê tổng quan"""
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Không thể kết nối database'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Đếm số lượng
        cur.execute("SELECT COUNT(*) AS cnt FROM garbage")
        n_garbage = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) AS cnt FROM road")
        n_road = cur.fetchone()['cnt']
        
        cur.execute("""
            SELECT "NATURE", COUNT(*) AS cnt, ROUND(SUM(area_m2)::numeric, 0) AS total_area
            FROM building GROUP BY "NATURE"
        """)
        buildings = cur.fetchall()
        
        # Diện tích vùng ảnh hưởng (buffer 100m)
        cur.execute("""
            SELECT ROUND(ST_Area(ST_Union(ST_Buffer(geom, 100)))::numeric, 0) AS impact_area
            FROM garbage
        """)
        impact = cur.fetchone()['impact_area']
        
        # Tòa nhà trong vòng 200m bãi rác
        cur.execute("""
            SELECT COUNT(DISTINCT b.gid) AS cnt
            FROM building b JOIN garbage g ON ST_DWithin(b.geom, g.geom, 200)
        """)
        buildings_200m = cur.fetchone()['cnt']
        
        return jsonify({
            'garbage_count': n_garbage,
            'road_segments': n_road,
            'buildings': [dict(r) for r in buildings],
            'impact_area_m2': impact,
            'buildings_within_200m': buildings_200m
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/query/buffer')
def query_buffer():
    """Tạo vùng đệm (buffer) quanh bãi rác"""
    radius = request.args.get('radius', 100, type=int)
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Không thể kết nối database'}), 500
    
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(feat)
            ) AS geojson
            FROM (
                SELECT json_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(ST_Transform(ST_Buffer(geom, %(r)s), 4326))::json,
                    'properties', json_build_object(
                        'id', gid,
                        'name', COALESCE(name, 'Bãi rác ' || gid),
                        'buffer_radius_m', %(r)s,
                        'buffer_area_m2', ROUND(ST_Area(ST_Buffer(geom, %(r)s))::numeric, 0)
                    )
                ) AS feat
                FROM garbage
            ) features
        """, {'r': radius})
        result = cur.fetchone()
        return jsonify(result['geojson'])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ============================================================
# Chạy app
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("  GIS Web App - Bãi rác Quang Hưng")
    print("  Mở trình duyệt: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
