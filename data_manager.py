import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

class DataManager:
    """資料管理器 - 處理請購單和採購單的持久化儲存"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.purchase_requests_file = os.path.join(data_dir, "purchase_requests.json")
        self.purchase_orders_file = os.path.join(data_dir, "purchase_orders.json")
        
        # 確保資料目錄存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 初始化檔案
        self._initialize_files()
    
    def _initialize_files(self):
        """初始化資料檔案"""
        if not os.path.exists(self.purchase_requests_file):
            self._save_json({}, self.purchase_requests_file)
            
        if not os.path.exists(self.purchase_orders_file):
            self._save_json({}, self.purchase_orders_file)
    
    def _save_json(self, data: Dict[str, Any], file_path: str):
        """儲存資料到 JSON 檔案"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"儲存資料失敗: {e}")
    
    def _load_json(self, file_path: str) -> Dict[str, Any]:
        """從 JSON 檔案載入資料"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"載入資料失敗: {e}")
            return {}
    
    def save_purchase_request(self, request_id: str, request_data: Dict[str, Any]):
        """儲存請購單"""
        requests = self._load_json(self.purchase_requests_file)
        requests[request_id] = request_data
        self._save_json(requests, self.purchase_requests_file)
    
    def get_purchase_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """取得特定請購單"""
        requests = self._load_json(self.purchase_requests_file)
        return requests.get(request_id)
    
    def get_all_purchase_requests(self) -> Dict[str, Any]:
        """取得所有請購單"""
        return self._load_json(self.purchase_requests_file)
    
    def update_purchase_request(self, request_id: str, updates: Dict[str, Any]):
        """更新請購單"""
        requests = self._load_json(self.purchase_requests_file)
        if request_id in requests:
            requests[request_id].update(updates)
            self._save_json(requests, self.purchase_requests_file)
            return True
        return False
    
    def save_purchase_order(self, order_id: str, order_data: Dict[str, Any]):
        """儲存採購單"""
        orders = self._load_json(self.purchase_orders_file)
        orders[order_id] = order_data
        self._save_json(orders, self.purchase_orders_file)
    
    def get_purchase_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """取得特定採購單"""
        orders = self._load_json(self.purchase_orders_file)
        return orders.get(order_id)
    
    def get_all_purchase_orders(self) -> Dict[str, Any]:
        """取得所有採購單"""
        return self._load_json(self.purchase_orders_file)
    
    def update_purchase_order(self, order_id: str, updates: Dict[str, Any]):
        """更新採購單"""
        orders = self._load_json(self.purchase_orders_file)
        if order_id in orders:
            orders[order_id].update(updates)
            self._save_json(orders, self.purchase_orders_file)
            return True
        return False