"""
GIS Web App - Bãi rác KCN Quang Hưng - Hải Phòng
Flask + PostGIS + Leaflet.js
5 layers: garbage | road | building | bounds | path_graph
"""
from flask import Flask, jsonify, render_template, request
import psycopg2, psycopg2.extras

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost', 'port': 5432,
    'database': 'quanghung_gis',
    'user': 'postgres',
    'password': '123456'   # ← SỬA password PostgreSQL của bạn
}

def get_db():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"DB error: {e}")
        return None

def fc(conn, sql, params=None):
    """Trả về FeatureCollection JSON"""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params or {})
    row = cur.fetchone()
    return row['geojson'] if row else {'type': 'FeatureCollection', 'features': []}

@app.route('/')
def index():
    return render_template('index.html')

# ── GeoJSON layers ───────────────────────────────────────────

@app.route('/api/garbage')
def api_garbage():
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        return jsonify(fc(conn, """
            SELECT json_build_object('type','FeatureCollection',
                'features', COALESCE(json_agg(f),'[]'::json)) AS geojson
            FROM (SELECT json_build_object('type','Feature',
                'geometry', ST_AsGeoJSON(ST_Transform(geom,4326))::json,
                'properties', json_build_object(
                    'id',gid,'name',COALESCE(name,'Bãi rác '||gid),
                    'category',COALESCE(category,'Công nghiệp'),
                    'lon',ROUND(ST_X(ST_Transform(geom,4326))::numeric,6),
                    'lat',ROUND(ST_Y(ST_Transform(geom,4326))::numeric,6)
                )) AS f FROM garbage) t
        """))
    finally: conn.close()

@app.route('/api/road')
def api_road():
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        return jsonify(fc(conn, """
            SELECT json_build_object('type','FeatureCollection',
                'features', COALESCE(json_agg(f),'[]'::json)) AS geojson
            FROM (SELECT json_build_object('type','Feature',
                'geometry', ST_AsGeoJSON(ST_Transform(geom,4326))::json,
                'properties', json_build_object(
                    'id',gid,'nb_lanes',"nbLanes",
                    'length_m',ROUND(length_m::numeric,1)
                )) AS f FROM road) t
        """))
    finally: conn.close()

@app.route('/api/building')
def api_building():
    nature = request.args.get('nature')
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        where = 'WHERE "NATURE"=%(n)s' if nature else ''
        return jsonify(fc(conn, f"""
            SELECT json_build_object('type','FeatureCollection',
                'features', COALESCE(json_agg(f),'[]'::json)) AS geojson
            FROM (SELECT json_build_object('type','Feature',
                'geometry', ST_AsGeoJSON(ST_Transform(geom,4326))::json,
                'properties', json_build_object(
                    'id',gid,'nature',"NATURE",'company',"COMPANY",
                    'area_m2',ROUND(area_m2::numeric,1),
                    'perim_m',ROUND(perim_m::numeric,1)
                )) AS f FROM building {where}) t
        """, {'n': nature}))
    finally: conn.close()

@app.route('/api/bounds')
def api_bounds():
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        return jsonify(fc(conn, """
            SELECT json_build_object('type','FeatureCollection',
                'features', COALESCE(json_agg(f),'[]'::json)) AS geojson
            FROM (SELECT json_build_object('type','Feature',
                'geometry', ST_AsGeoJSON(ST_Transform(geom,4326))::json,
                'properties', json_build_object('id',gid)) AS f FROM bounds) t
        """))
    finally: conn.close()

@app.route('/api/pathgraph')
def api_pathgraph():
    """Layer path_graph - topology graph của GAMA Garbage Path Finder"""
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        return jsonify(fc(conn, """
            SELECT json_build_object('type','FeatureCollection',
                'features', COALESCE(json_agg(f),'[]'::json)) AS geojson
            FROM (SELECT json_build_object('type','Feature',
                'geometry', ST_AsGeoJSON(ST_Transform(geom,4326))::json,
                'properties', json_build_object(
                    'id',gid,'length_m',ROUND(length_m::numeric,1)
                )) AS f FROM path_graph) t
        """))
    finally: conn.close()

# ── Spatial Queries ──────────────────────────────────────────

@app.route('/api/query/stats')
def query_stats():
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) AS c FROM garbage");      n_g  = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM road");         n_r  = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM path_graph");   n_pg = cur.fetchone()['c']
        cur.execute("SELECT ROUND(SUM(length_m)::numeric,0) AS t FROM road"); road_km = cur.fetchone()['t']
        cur.execute("""SELECT "NATURE" AS nature, COUNT(*) AS cnt,
                       ROUND(SUM(area_m2)::numeric,0) AS total_area
                       FROM building GROUP BY "NATURE" """)
        buildings = cur.fetchall()
        cur.execute("""SELECT ROUND(ST_Area(ST_Union(ST_Buffer(geom,100)))::numeric,0) AS a FROM garbage""")
        impact = cur.fetchone()['a']
        cur.execute("""SELECT COUNT(DISTINCT b.gid) AS c FROM building b
                       JOIN garbage g ON ST_DWithin(b.geom,g.geom,200)""")
        near200 = cur.fetchone()['c']
        return jsonify({
            'garbage_count': n_g, 'road_segments': n_r,
            'road_total_m': road_km, 'path_graph_edges': n_pg,
            'buildings': [dict(r) for r in buildings],
            'impact_area_m2': impact, 'buildings_200m': near200
        })
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: conn.close()

@app.route('/api/query/nearby-buildings')
def query_nearby():
    radius = request.args.get('radius', 200, type=int)
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT DISTINCT b.gid,"NATURE" AS nature,"COMPANY" AS company,
                   ROUND(b.area_m2::numeric,1) AS area_m2,
                   ROUND(MIN(ST_Distance(b.geom,g.geom))::numeric,1) AS min_dist_m,
                   ST_AsGeoJSON(ST_Transform(b.geom,4326))::json AS geometry
            FROM building b JOIN garbage g ON ST_DWithin(b.geom,g.geom,%(r)s)
            GROUP BY b.gid,b."NATURE",b."COMPANY",b.area_m2,b.geom
            ORDER BY min_dist_m
        """, {'r': radius})
        rows = cur.fetchall()
        return jsonify({'type':'FeatureCollection','features':[{
            'type':'Feature','geometry':r['geometry'],
            'properties':{'id':r['gid'],'nature':r['nature'],'company':r['company'],
                          'area_m2':r['area_m2'],'min_dist_m':r['min_dist_m']}
        } for r in rows],'query_info':{'radius_m':radius,'total':len(rows)}})
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: conn.close()

@app.route('/api/query/buffer')
def query_buffer():
    radius = request.args.get('radius', 100, type=int)
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        return jsonify(fc(conn, """
            SELECT json_build_object('type','FeatureCollection','features',json_agg(f)) AS geojson
            FROM (SELECT json_build_object('type','Feature',
                'geometry', ST_AsGeoJSON(ST_Transform(ST_Buffer(geom,%(r)s),4326))::json,
                'properties', json_build_object(
                    'id',gid,'name',COALESCE(name,'Bãi rác '||gid),
                    'radius_m',%(r)s,
                    'area_m2',ROUND(ST_Area(ST_Buffer(geom,%(r)s))::numeric,0)
                )) AS f FROM garbage) t
        """, {'r': radius}))
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: conn.close()

@app.route('/api/query/nearest-road')
def query_nearest_road():
    conn = get_db()
    if not conn: return jsonify({'error': 'DB offline'}), 500
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT g.gid, g.name, r.gid AS road_id, r."nbLanes" AS lanes,
                   ROUND(ST_Distance(g.geom,r.geom)::numeric,2) AS dist_m,
                   ST_AsGeoJSON(ST_Transform(r.geom,4326))::json AS geometry
            FROM garbage g CROSS JOIN LATERAL (
                SELECT gid,geom,"nbLanes" FROM road ORDER BY g.geom<->geom LIMIT 1
            ) r
        """)
        rows = cur.fetchall()
        return jsonify({'type':'FeatureCollection','features':[{
            'type':'Feature','geometry':r['geometry'],
            'properties':{'garbage_id':r['gid'],'name':r['name'],
                          'road_id':r['road_id'],'lanes':r['lanes'],'dist_m':r['dist_m']}
        } for r in rows]})
    except Exception as e: return jsonify({'error': str(e)}), 500
    finally: conn.close()

if __name__ == '__main__':
    print("  GIS App → http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
