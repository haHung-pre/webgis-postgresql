# GIS Web App – Bãi rác KCN Quang Hưng, Hải Phòng
## GAMA Garbage Path Finder | PostgreSQL + PostGIS + Flask + Leaflet.js

## Cấu trúc
```
gis-app/
├── app.py              ← Flask REST API (5 layer endpoints + spatial queries)
├── requirements.txt    ← Python deps
├── import_data.py      ← Script import shapefile (thay thế shp2pgsql)
├── README.md
├── sql/
│   ├── 01_setup.sql    ← Tạo DB + PostGIS extension
│   ├── 02_import.sql   ← shp2pgsql commands + chuẩn bị cột
│   └── 03_queries.sql  ← 18 spatial queries
├── templates/
│   └── index.html      ← Leaflet.js map (5 layers + 3 query tools)
└── data/               ← GeoJSON pre-converted (backup không cần DB)
    ├── garbadge.geojson
    ├── road.geojson
    ├── building.geojson
    ├── bounds.geojson
    └── instruction-generated.geojson
```

## 5 Layers
| Layer        | File gốc                   | Geometry   | Bản ghi | Ghi chú                          |
|--------------|---------------------------|------------|---------|----------------------------------|
| garbage      | garbadge.shp              | Point      | 11      | Điểm bãi rác công nghiệp         |
| road         | road.shp                  | LineString | 110     | Mạng đường nội khu (nbLanes)     |
| building     | building.shp              | Polygon    | 174     | Tòa nhà (Residential/Industrial) |
| bounds       | bounds.shp                | Polygon    | 1       | Ranh giới khu vực                |
| path_graph   | instruction-generated.shp | LineString | 110     | Topology graph GAMA Path Finder  |

## Chạy nhanh (Windows)

```bash
# 1. Import shapefile (CMD trong thư mục includes/)
shp2pgsql -I -s 32648 garbadge.shp           public.garbage      | psql -U postgres -d quanghung_gis
shp2pgsql -I -s 32648 road.shp               public.road         | psql -U postgres -d quanghung_gis
shp2pgsql -I -s 32648 building.shp           public.building     | psql -U postgres -d quanghung_gis
shp2pgsql -I -s 32648 bounds.shp             public.bounds       | psql -U postgres -d quanghung_gis
shp2pgsql -I -s 32648 instruction-generated.shp public.path_graph | psql -U postgres -d quanghung_gis

# Hoặc dùng Python:
python import_data.py

# 2. Cài Flask
pip install flask psycopg2-binary

# 3. Chạy app (sửa password trong app.py trước)
python app.py  →  http://localhost:5000
```

## API Endpoints
| Endpoint | Mô tả |
|----------|-------|
| GET /api/garbage | GeoJSON – bãi rác (11 points) |
| GET /api/road | GeoJSON – đường đi (110 lines) |
| GET /api/building?nature=Industrial | GeoJSON – tòa nhà (filter by nature) |
| GET /api/bounds | GeoJSON – ranh giới |
| GET /api/pathgraph | GeoJSON – path graph GAMA |
| GET /api/query/stats | Thống kê tổng quan |
| GET /api/query/nearby-buildings?radius=200 | ST_DWithin |
| GET /api/query/buffer?radius=100 | ST_Buffer |
| GET /api/query/nearest-road | Nearest road per garbage |

## Truy vấn SQL thường gặp (thầy hay hỏi)
- ST_Distance, ST_DWithin, ST_Buffer, ST_Within, ST_Intersects
- ST_Transform (32648 → 4326), ST_AsGeoJSON
- ST_Centroid, ST_ConvexHull, ST_Union, ST_Extent
- Nearest neighbor: ORDER BY geom <-> geom LIMIT 1
