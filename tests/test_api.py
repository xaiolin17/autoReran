import pytest
from datetime import datetime


@pytest.mark.integration
class TestHealthCheck:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "股票数据分析平台运行正常" in data["message"]
    
    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200


@pytest.mark.integration
class TestMetricsEndpoint:
    def test_metrics_endpoint(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200


@pytest.mark.integration
class TestStockEndpoints:
    def test_get_available_stocks_empty(self, client):
        response = client.get("/api/v1/stocks")
        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
    
    def test_get_stock_data_not_found(self, client):
        response = client.get("/api/v1/stocks/NONEXISTENT")
        assert response.status_code == 200


@pytest.mark.integration
class TestAdvancedEndpoints:
    def test_list_tasks_empty(self, client):
        response = client.get("/api/v1/advanced/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
    
    def test_list_backups_empty(self, client):
        response = client.get("/api/v1/advanced/backup/list")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "backups" in data
