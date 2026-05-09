import csv
import io
import os
from datetime import datetime
from typing import List, Any, Dict
from fastapi import Response
import openpyxl
from app.core.config import settings
from app.core.logger import logger


def export_to_csv(data: List[Dict[str, Any]], filename: str = "export.csv") -> Response:
    if not data:
        return Response(content="No data to export", status_code=400)
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def export_to_excel(data: List[Dict[str, Any]], filename: str = "export.xlsx", sheet_name: str = "Sheet1") -> Response:
    if not data:
        return Response(content="No data to export", status_code=400)
    
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    
    headers = list(data[0].keys())
    worksheet.append(headers)
    
    for row in data:
        worksheet.append([str(row.get(key, "")) for key in headers])
    
    workbook.save(output)
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def ensure_backup_dir():
    if not os.path.exists(settings.BACKUP_DIR):
        os.makedirs(settings.BACKUP_DIR)


def create_backup(data: str, backup_type: str = "data") -> str:
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{backup_type}_{timestamp}.json"
    filepath = os.path.join(settings.BACKUP_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data)
    
    logger.info(f"备份创建成功: {filepath}")
    return filepath


def list_backups() -> List[Dict[str, Any]]:
    ensure_backup_dir()
    backups = []
    for filename in os.listdir(settings.BACKUP_DIR):
        filepath = os.path.join(settings.BACKUP_DIR, filename)
        if os.path.isfile(filepath):
            stats = os.stat(filepath)
            backups.append({
                "filename": filename,
                "size": stats.st_size,
                "created_at": datetime.fromtimestamp(stats.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stats.st_mtime).isoformat(),
            })
    return sorted(backups, key=lambda x: x["created_at"], reverse=True)
