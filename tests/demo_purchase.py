#!/usr/bin/env python3
"""
簡化的請購系統示例

這個腳本展示如何使用請購系統的核心功能：
1. 分析請購需求
2. 獲取採購歷史
3. 生成產品推薦
4. 創建並提交請購單
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# 將父目錄加入 Python 路徑，讓測試可以導入根目錄的模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from purchase_agent import PurchaseAgent, PurchaseAgentConfig


def simple_purchase_demo():
    """簡單的請購演示"""
    load_dotenv()

    # 檢查環境變數
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 請設定 OPENAI_API_KEY 環境變數")
        return

    print("🚀 SAP 請購系統演示")
    print("=" * 50)

    # 建立配置
    config = PurchaseAgentConfig(
        api_base_url="http://localhost:7777",
        model="gpt-4o-mini",
        openai_api_key=api_key,
    )

    # 檢查API服務
    try:
        response = requests.get(f"{config.api_base_url}/", timeout=5)
        if response.status_code != 200:
            print("❌ SAP API 服務器未運行，請先執行: python app.py")
            return
        print("✅ SAP API 服務器運行正常")
    except:
        print("❌ 無法連接到 SAP API 服務器，請先執行: python app.py")
        return

    # 建立 Agent
    agent = PurchaseAgent(config)

    # 示例請購需求
    examples = [
        {
            "name": "軟體開發部門筆電需求",
            "request": "我需要為軟體開發部門採購新的筆記型電腦，要求MacBook Pro，記憶體16GB以上，需要3台，預算每台7.5萬元。",
        },
        {
            "name": "設計部門顯示器需求",
            "request": "設計部門需要4K顯示器，27吋，需要5台，預算每台2萬元以內。",
        },
        {
            "name": "行銷部門平板需求",
            "request": "行銷部門需要iPad Pro用於客戶展示，12.9吋，需要2台。",
        },
    ]

    print("\n📋 可用的示例請購需求：")
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example['name']}")

    # 讓使用者選擇或輸入自訂需求
    print("\n選擇測試方式：")
    print("1-3: 選擇示例")
    print("4: 輸入自訂需求")

    choice = input("請輸入選擇 (1-4): ").strip()

    if choice in ["1", "2", "3"]:
        selected = examples[int(choice) - 1]
        request_text = selected["request"]
        print(f"\n📝 已選擇: {selected['name']}")
    elif choice == "4":
        request_text = input("\n請輸入您的請購需求: ").strip()
        if not request_text:
            print("❌ 請輸入有效的請購需求")
            return
    else:
        print("❌ 無效選擇")
        return

    print(f"\n🎯 處理請購需求: {request_text}")
    print("=" * 50)

    # 處理請購
    try:
        result, tokens = agent.process_purchase_request(request_text)

        print(f"\n📊 處理結果:")
        print(f"Token 使用量: {tokens}")
        print(f"處理狀態: {'成功' if result.get('generation') else '失敗'}")

        # 顯示請購單號（如果有的話）
        if "api_response" in result and "request_id" in result["api_response"]:
            request_id = result["api_response"]["request_id"]
            print(f"📄 請購單號: {request_id}")

            # 查詢請購單狀態
            print("\n🔍 查詢請購單狀態...")
            status_response = requests.get(
                f"{config.api_base_url}/api/purchase-request/{request_id}"
            )
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"狀態: {status_data['data']['status']}")
                print(f"創建時間: {status_data['data']['created_date']}")

    except Exception as e:
        print(f"❌ 處理失敗: {e}")

    print("\n✅ 演示完成！")


if __name__ == "__main__":
    simple_purchase_demo()
