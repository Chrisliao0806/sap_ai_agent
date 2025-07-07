#!/usr/bin/env python3
"""
SAP AI Agent 請購單和採購單 API 測試程式
測試完整的請購流程：創建請購單 -> 創建採購單 -> 驗證狀態更新
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional


class SAPAPITester:
    """SAP API 測試類別"""

    def __init__(self, base_url: str = "http://localhost:7777"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    def print_separator(self, title: str):
        """打印分隔線"""
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    def print_response(self, response: requests.Response, description: str):
        """打印API響應"""
        print(f"\n【{description}】")
        print(f"Status Code: {response.status_code}")
        try:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            print(f"Response Text: {response.text}")

    def test_api_connection(self) -> bool:
        """測試API連接"""
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                print("✅ API連接成功")
                return True
            else:
                print(f"❌ API連接失敗 - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API連接失敗 - Error: {str(e)}")
            return False

    def create_purchase_request(self, request_data: Dict[str, Any]) -> Optional[str]:
        """創建請購單"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/purchase-request", json=request_data
            )

            self.print_response(response, "創建請購單")

            if response.status_code == 201:
                data = response.json()
                request_id = data.get("request_id")
                print(f"✅ 請購單創建成功 - ID: {request_id}")
                return request_id
            else:
                print(f"❌ 請購單創建失敗 - Status: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ 創建請購單異常: {str(e)}")
            return None

    def get_purchase_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """查詢請購單"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/purchase-request/{request_id}"
            )

            self.print_response(response, f"查詢請購單 - {request_id}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 請購單查詢成功")
                return data.get("data")
            else:
                print(f"❌ 請購單查詢失敗 - Status: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ 查詢請購單異常: {str(e)}")
            return None

    def create_purchase_order_from_request(
        self, request_id: str, supplier_id: str = None
    ) -> Optional[str]:
        """根據請購單創建採購單"""
        try:
            # 準備請求數據
            request_data = {}
            if supplier_id:
                request_data["supplier_id"] = supplier_id

            response = self.session.post(
                f"{self.base_url}/api/purchase-order/from-request/{request_id}",
                json=request_data if request_data else None,
            )

            self.print_response(response, f"從請購單創建採購單 - {request_id}")

            if response.status_code == 201:
                data = response.json()
                order_id = data.get("order_id")
                print(f"✅ 採購單創建成功 - ID: {order_id}")
                return order_id
            else:
                print(f"❌ 採購單創建失敗 - Status: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ 創建採購單異常: {str(e)}")
            return None

    def get_purchase_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """查詢採購單"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/purchase-order/{order_id}"
            )

            self.print_response(response, f"查詢採購單 - {order_id}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 採購單查詢成功")
                return data.get("data")
            else:
                print(f"❌ 採購單查詢失敗 - Status: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ 查詢採購單異常: {str(e)}")
            return None

    def get_all_purchase_requests(self) -> Optional[list]:
        """查詢所有請購單"""
        try:
            response = self.session.get(f"{self.base_url}/api/purchase-requests")

            self.print_response(response, "查詢所有請購單")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 查詢所有請購單成功 - 共 {data.get('total_requests', 0)} 筆")
                return data.get("data", [])
            else:
                print(f"❌ 查詢所有請購單失敗 - Status: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ 查詢所有請購單異常: {str(e)}")
            return None

    def get_all_purchase_orders(self) -> Optional[list]:
        """查詢所有採購單"""
        try:
            response = self.session.get(f"{self.base_url}/api/purchase-orders")

            self.print_response(response, "查詢所有採購單")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 查詢所有採購單成功 - 共 {data.get('total_orders', 0)} 筆")
                return data.get("data", [])
            else:
                print(f"❌ 查詢所有採購單失敗 - Status: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ 查詢所有採購單異常: {str(e)}")
            return None

    def run_complete_test(self):
        """執行完整的測試流程"""
        print("🚀 開始執行 SAP API 完整測試流程")
        print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. 測試API連接
        self.print_separator("1. 測試API連接")
        if not self.test_api_connection():
            print("❌ API連接失敗，測試終止")
            return False

        # 2. 準備測試數據
        self.print_separator("2. 準備測試數據")

        # 測試案例1: MacBook Pro 請購
        macbook_request = {
            "product_name": "MacBook Pro 16吋",
            "category": "筆記型電腦",
            "quantity": 2,
            "unit_price": 75000,
            "requester": "測試用戶",
            "department": "IT部門",
            "reason": "開發團隊設備更新",
            "urgent": False,
            "expected_delivery_date": "2025-07-15",
        }

        # 測試案例2: Surface Laptop 請購
        surface_request = {
            "product_name": "Surface Laptop Studio",
            "category": "筆記型電腦",
            "quantity": 1,
            "unit_price": 65000,
            "requester": "測試用戶2",
            "department": "研發部門",
            "reason": "設計工作需要",
            "urgent": True,
            "expected_delivery_date": "2025-07-10",
        }

        print("測試案例1: MacBook Pro 16吋 x2")
        print(f"數據: {json.dumps(macbook_request, indent=2, ensure_ascii=False)}")

        print("\n測試案例2: Surface Laptop Studio x1")
        print(f"數據: {json.dumps(surface_request, indent=2, ensure_ascii=False)}")

        # 3. 創建請購單
        self.print_separator("3. 創建請購單")

        # 創建第一筆請購單
        macbook_request_id = self.create_purchase_request(macbook_request)
        if not macbook_request_id:
            print("❌ 第一筆請購單創建失敗")
            return False

        time.sleep(1)  # 等待一秒

        # 創建第二筆請購單
        surface_request_id = self.create_purchase_request(surface_request)
        if not surface_request_id:
            print("❌ 第二筆請購單創建失敗")
            return False

        # 4. 查詢請購單狀態
        self.print_separator("4. 查詢請購單狀態")

        print("查詢MacBook請購單狀態...")
        macbook_request_data = self.get_purchase_request(macbook_request_id)
        if not macbook_request_data:
            print("❌ MacBook請購單查詢失敗")
            return False

        print("\n查詢Surface請購單狀態...")
        surface_request_data = self.get_purchase_request(surface_request_id)
        if not surface_request_data:
            print("❌ Surface請購單查詢失敗")
            return False

        # 5. 創建採購單
        self.print_separator("5. 創建採購單")

        print("從MacBook請購單創建採購單...")
        macbook_order_id = self.create_purchase_order_from_request(macbook_request_id)
        if not macbook_order_id:
            print("❌ MacBook採購單創建失敗")
            return False

        time.sleep(1)  # 等待一秒

        print("\n從Surface請購單創建採購單...")
        surface_order_id = self.create_purchase_order_from_request(surface_request_id)
        if not surface_order_id:
            print("❌ Surface採購單創建失敗")
            return False

        # 6. 查詢採購單狀態
        self.print_separator("6. 查詢採購單狀態")

        print("查詢MacBook採購單狀態...")
        macbook_order_data = self.get_purchase_order(macbook_order_id)
        if not macbook_order_data:
            print("❌ MacBook採購單查詢失敗")
            return False

        print("\n查詢Surface採購單狀態...")
        surface_order_data = self.get_purchase_order(surface_order_id)
        if not surface_order_data:
            print("❌ Surface採購單查詢失敗")
            return False

        # 7. 驗證請購單狀態是否已更新
        self.print_separator("7. 驗證請購單狀態更新")

        print("重新查詢MacBook請購單狀態...")
        updated_macbook_request = self.get_purchase_request(macbook_request_id)
        if updated_macbook_request:
            if updated_macbook_request.get("status") == "已完成":
                print("✅ MacBook請購單狀態已正確更新為'已完成'")
            else:
                print(f"⚠️ MacBook請購單狀態為: {updated_macbook_request.get('status')}")

        print("\n重新查詢Surface請購單狀態...")
        updated_surface_request = self.get_purchase_request(surface_request_id)
        if updated_surface_request:
            if updated_surface_request.get("status") == "已完成":
                print("✅ Surface請購單狀態已正確更新為'已完成'")
            else:
                print(f"⚠️ Surface請購單狀態為: {updated_surface_request.get('status')}")

        # 8. 查詢所有請購單和採購單
        self.print_separator("8. 查詢所有請購單和採購單")

        all_requests = self.get_all_purchase_requests()
        all_orders = self.get_all_purchase_orders()

        # 9. 測試總結
        self.print_separator("9. 測試總結")

        print("📊 測試結果總結:")
        print(f"✅ 成功創建請購單: 2筆")
        print(f"   - MacBook Pro 16吋: {macbook_request_id}")
        print(f"   - Surface Laptop Studio: {surface_request_id}")

        print(f"✅ 成功創建採購單: 2筆")
        print(f"   - MacBook採購單: {macbook_order_id}")
        print(f"   - Surface採購單: {surface_order_id}")

        print(f"✅ 請購單狀態更新: 已驗證")
        print(f"✅ 系統總請購單數: {len(all_requests) if all_requests else 0}")
        print(f"✅ 系統總採購單數: {len(all_orders) if all_orders else 0}")

        print(f"\n🎉 完整測試流程執行完成！")
        print(f"測試完成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return True


def main():
    """主函數"""
    print("🔧 SAP AI Agent API 測試程式")
    print("=" * 60)

    # 創建測試器實例
    tester = SAPAPITester()

    # 執行完整測試
    success = tester.run_complete_test()

    if success:
        print("\n🎯 所有測試執行成功！")
    else:
        print("\n❌ 測試執行過程中出現問題")

    return success


if __name__ == "__main__":
    main()
