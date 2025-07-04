"""
對話式請購系統測試

這個測試文件會模擬完整的請購流程，包括：
1. 新請購需求
2. 確認推薦
3. 調整推薦
4. 確認請購單
5. 提交請購單
6. 偏離主題的對話
"""

import requests
import json
import time
import os
from datetime import datetime

# 設定 API 基礎 URL
API_BASE_URL = "http://localhost:7777"


def test_chat_interaction():
    """測試對話式交互"""
    print("🚀 開始測試對話式請購系統...")

    # 測試場景
    test_scenarios = [
        {
            "name": "新請購需求",
            "message": "我需要採購一台筆記型電腦，用於開發工作",
            "session_id": "test_user_001",
        },
        {"name": "確認推薦", "message": "同意", "session_id": "test_user_001"},
        {"name": "確認提交", "message": "確認提交", "session_id": "test_user_001"},
        {
            "name": "新需求 - 調整流程",
            "message": "我需要採購平板電腦，預算3萬元",
            "session_id": "test_user_002",
        },
        {
            "name": "要求調整",
            "message": "不同意，我要更便宜的選項",
            "session_id": "test_user_002",
        },
        {
            "name": "確認調整後的推薦",
            "message": "好的，同意這個推薦",
            "session_id": "test_user_002",
        },
        {
            "name": "偏離主題測試",
            "message": "今天天氣真好",
            "session_id": "test_user_003",
        },
        {
            "name": "引導回採購",
            "message": "我需要採購手機",
            "session_id": "test_user_003",
        },
    ]

    for i, scenario in enumerate(test_scenarios):
        print(f"\n--- 測試場景 {i + 1}: {scenario['name']} ---")

        try:
            # 發送對話請求
            response = requests.post(
                f"{API_BASE_URL}/api/chat",
                json={
                    "message": scenario["message"],
                    "session_id": scenario["session_id"],
                },
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 狀態: {data['status']}")
                print(f"📝 回應: {data['response']}")
                print(f"🔄 對話狀態: {data['conversation_state']}")
                print(f"💡 有推薦: {data['has_recommendation']}")
                print(f"📋 有確認單: {data['has_confirmed_order']}")
            else:
                print(f"❌ 請求失敗: {response.status_code}")
                print(f"錯誤訊息: {response.text}")

        except Exception as e:
            print(f"❌ 測試失敗: {e}")

        # 等待一秒避免請求過快
        time.sleep(1)


def test_session_management():
    """測試會話管理"""
    print("\n🔧 測試會話管理功能...")

    # 創建測試會話
    session_id = "test_session_mgmt"

    # 發送測試訊息
    requests.post(
        f"{API_BASE_URL}/api/chat",
        json={"message": "我要採購筆電", "session_id": session_id},
    )

    # 測試獲取會話狀態
    try:
        response = requests.get(f"{API_BASE_URL}/api/chat/session/{session_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 會話狀態獲取成功")
            print(
                f"📊 會話資料: {json.dumps(data['data'], indent=2, ensure_ascii=False)}"
            )
        else:
            print(f"❌ 會話狀態獲取失敗: {response.status_code}")
    except Exception as e:
        print(f"❌ 會話狀態測試失敗: {e}")

    # 測試重置會話
    try:
        response = requests.delete(f"{API_BASE_URL}/api/chat/session/{session_id}")
        if response.status_code == 200:
            print(f"✅ 會話重置成功")
        else:
            print(f"❌ 會話重置失敗: {response.status_code}")
    except Exception as e:
        print(f"❌ 會話重置測試失敗: {e}")


def test_multiple_sessions():
    """測試多會話並行"""
    print("\n👥 測試多會話並行...")

    sessions = ["user_a", "user_b", "user_c"]
    messages = ["我需要採購 MacBook", "我要買 Surface", "我想要平板電腦"]

    # 同時創建多個會話
    for session_id, message in zip(sessions, messages):
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/chat",
                json={"message": message, "session_id": session_id},
            )
            if response.status_code == 200:
                print(f"✅ 會話 {session_id} 創建成功")
            else:
                print(f"❌ 會話 {session_id} 創建失敗")
        except Exception as e:
            print(f"❌ 會話 {session_id} 測試失敗: {e}")

    # 測試獲取所有會話
    try:
        response = requests.get(f"{API_BASE_URL}/api/chat/sessions")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 所有會話獲取成功")
            print(f"📊 會話總數: {data['total_sessions']}")
            for session in data["data"]:
                print(f"  - {session['session_id']}: {session['conversation_state']}")
        else:
            print(f"❌ 所有會話獲取失敗: {response.status_code}")
    except Exception as e:
        print(f"❌ 所有會話測試失敗: {e}")


def test_api_endpoints():
    """測試原有的 API 端點"""
    print("\n🔗 測試原有 API 端點...")

    endpoints = ["/api/purchase-history", "/api/inventory", "/"]

    for endpoint in endpoints:
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}")
            if response.status_code == 200:
                print(f"✅ {endpoint} 正常運作")
            else:
                print(f"❌ {endpoint} 異常: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} 測試失敗: {e}")


def main():
    """主要測試函數"""
    print("=" * 60)
    print("🧪 SAP 對話式請購系統 - 完整測試")
    print("=" * 60)

    # 檢查環境變數
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  警告: 未設定 OPENAI_API_KEY 環境變數")
        print("請先設定 OpenAI API Key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return

    # 檢查 API 伺服器是否運行
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code != 200:
            print(f"❌ API 伺服器無法連接: {API_BASE_URL}")
            print("請先啟動 API 伺服器: python app.py")
            return
    except Exception as e:
        print(f"❌ API 伺服器連接失敗: {e}")
        print("請先啟動 API 伺服器: python app.py")
        return

    print(f"✅ API 伺服器運行正常: {API_BASE_URL}")

    # 執行測試
    test_chat_interaction()
    test_session_management()
    test_multiple_sessions()
    test_api_endpoints()

    print("\n" + "=" * 60)
    print("🎉 測試完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
