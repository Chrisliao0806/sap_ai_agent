import requests
import json

# API 基礎 URL
BASE_URL = "http://localhost:7777"


def test_apis():
    """測試所有 API 端點"""
    print("🧪 開始測試假 SAP API 系統")
    print("=" * 50)

    # 1. 測試首頁
    print("\n1️⃣ 測試 API 首頁")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"狀態碼: {response.status_code}")
        print(f"回應: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"錯誤: {e}")

    # 2. 測試採購歷史 API
    print("\n2️⃣ 測試採購歷史 API")
    try:
        response = requests.get(f"{BASE_URL}/api/purchase-history")
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"總記錄數: {data['total_records']}")
        print(
            f"第一筆採購記錄: {json.dumps(data['data'][0], ensure_ascii=False, indent=2)}"
        )
    except Exception as e:
        print(f"錯誤: {e}")

    # 3. 測試篩選採購歷史（按類別）
    print("\n3️⃣ 測試篩選採購歷史（筆記型電腦）")
    try:
        response = requests.get(f"{BASE_URL}/api/purchase-history?category=筆記型電腦")
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"篩選後記錄數: {data['total_records']}")
    except Exception as e:
        print(f"錯誤: {e}")

    # 4. 測試採購詳細資訊
    print("\n4️⃣ 測試採購詳細資訊")
    try:
        response = requests.get(f"{BASE_URL}/api/purchase-history/PH001")
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"詳細資訊: {json.dumps(data['data'], ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"錯誤: {e}")

    # 5. 測試庫存資訊 API
    print("\n5️⃣ 測試庫存資訊 API")
    try:
        response = requests.get(f"{BASE_URL}/api/inventory")
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"總商品數: {data['total_items']}")
        print(f"總庫存價值: NT$ {data['total_inventory_value']:,}")
        print(
            f"第一個商品: {json.dumps(data['data'][0], ensure_ascii=False, indent=2)}"
        )
    except Exception as e:
        print(f"錯誤: {e}")

    # 6. 測試低庫存查詢
    print("\n6️⃣ 測試低庫存查詢")
    try:
        response = requests.get(f"{BASE_URL}/api/inventory?low_stock=true")
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"低庫存商品數: {data['total_items']}")
    except Exception as e:
        print(f"錯誤: {e}")

    # 7. 測試特定產品庫存
    print("\n7️⃣ 測試特定產品庫存")
    try:
        response = requests.get(f"{BASE_URL}/api/inventory/INV001")
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"產品庫存詳情: {json.dumps(data['data'], ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"錯誤: {e}")

    # 8. 測試創建請購單
    print("\n8️⃣ 測試創建請購單")
    try:
        purchase_data = {
            "product_name": "MacBook Air M3",
            "category": "筆記型電腦",
            "quantity": 3,
            "unit_price": 45000,
            "requester": "測試用戶",
            "department": "測試部門",
            "reason": "部門擴編需求",
            "urgent": False,
            "expected_delivery_date": "2025-02-15",
        }

        response = requests.post(
            f"{BASE_URL}/api/purchase-request",
            json=purchase_data,
            headers={"Content-Type": "application/json"},
        )
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"請購單ID: {data.get('request_id')}")
        print(f"創建結果: {json.dumps(data, ensure_ascii=False, indent=2)}")

        # 保存請購單ID以供後續測試
        global test_request_id
        test_request_id = data.get("request_id")

    except Exception as e:
        print(f"錯誤: {e}")

    # 9. 測試查詢請購單
    print("\n9️⃣ 測試查詢請購單狀態")
    try:
        if "test_request_id" in globals():
            response = requests.get(
                f"{BASE_URL}/api/purchase-request/{test_request_id}"
            )
            print(f"狀態碼: {response.status_code}")
            data = response.json()
            print(f"請購單狀態: {data['data']['status']}")
            print(
                f"審核軌跡: {json.dumps(data['data']['approval_trail'], ensure_ascii=False, indent=2)}"
            )
    except Exception as e:
        print(f"錯誤: {e}")

    # 10. 測試查詢所有請購單
    print("\n🔟 測試查詢所有請購單")
    try:
        response = requests.get(f"{BASE_URL}/api/purchase-requests")
        print(f"狀態碼: {response.status_code}")
        data = response.json()
        print(f"總請購單數: {data['total_requests']}")
    except Exception as e:
        print(f"錯誤: {e}")

    print("\n✅ API 測試完成!")


if __name__ == "__main__":
    print("請確保 API 服務器正在運行 (python app.py)")
    print("然後執行此測試腳本...")

    # 等待用戶確認
    input("按 Enter 開始測試...")
    test_apis()
