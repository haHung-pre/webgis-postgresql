# GIS Web App - Bãi rác KCN Quang Hưng

## Cấu trúc thư mục
```
gis-app/
├── app.py              ← Flask backend (REST API)
├── requirements.txt    ← Thư viện Python cần cài
├── import_data.py      ← Script import shapefile (thay thế shp2pgsql)
├── sql/
│   ├── 01_setup.sql    ← Tạo database + extension PostGIS
│   ├── 02_import.sql   ← Hướng dẫn import + chuẩn bị dữ liệu
│   └── 03_queries.sql  ← 12 truy vấn không gian đầy đủ
├── templates/
│   └── index.html      ← Giao diện bản đồ Leaflet.js
└── data/               ← GeoJSON (dùng nếu không có PostgreSQL)
```

## Cách chạy (Windows)

### Bước 1: Cài PostgreSQL + PostGIS
- Tải PostgreSQL: https://www.postgresql.org/download/windows/
- Trong Stack Builder → chọn PostGIS

### Bước 2: Tạo database
```sql
CREATE DATABASE quanghung_gis;
\c quanghung_gis
CREATE EXTENSION postgis;
```

### Bước 3: Import shapefile
```bash
# Dùng shp2pgsql (trong thư mục includes/):
shp2pgsql -I -s 32648 garbadge.shp public.garbage | psql -U postgres -d quanghung_gis
shp2pgsql -I -s 32648 road.shp public.road | psql -U postgres -d quanghung_gis
shp2pgsql -I -s 32648 building.shp public.building | psql -U postgres -d quanghung_gis
shp2pgsql -I -s 32648 bounds.shp public.bounds | psql -U postgres -d quanghung_gis
```

### Bước 4: Chạy web app
```bash
pip install -r requirements.txt
python app.py
# Mở: http://localhost:5000
```

## API Endpoints
| Endpoint | Mô tả |
|----------|-------|
| GET /api/garbage | GeoJSON bãi rác |
| GET /api/road | GeoJSON đường đi |
| GET /api/building | GeoJSON tòa nhà |
| GET /api/bounds | GeoJSON ranh giới |
| GET /api/query/stats | Thống kê tổng quan |
| GET /api/query/nearby-buildings?radius=200 | Tòa nhà gần bãi rác (ST_DWithin) |
| GET /api/query/buffer?radius=100 | Vùng đệm Buffer (ST_Buffer) |
