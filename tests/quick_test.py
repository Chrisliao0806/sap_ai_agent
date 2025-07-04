#!/usr/bin/env python3
"""
快速測試請購系統

用於驗證請購系統基本功能是否正常運作
"""

import os
import sys
from dotenv import load_dotenv

# 將父目錄加入 Python 路徑，讓測試可以導入根目錄的模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from purchase_agent import PurchaseAgent, PurchaseAgentConfig


def quick_test():
    """快速測試請購系統"""
    load_dotenv()

    # 檢查環境變數
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 請設定 OPENAI_API_KEY 環境變數")
        return False

    print("🚀 快速測試請購系統")
    print("=" * 40)

    # 建立配置
    config = PurchaseAgentConfig(
        api_base_url="http://localhost:7777",
        model="gpt-4o-mini",
        openai_api_key=api_key,
    )

    # 建立 Agent
    try:
        agent = PurchaseAgent(config)
        print("✅ Agent 建立成功")
    except Exception as e:
        print(f"❌ Agent 建立失敗: {e}")
        return False

    # 測試請購需求
    test_request = "我需要採購筆記型電腦，MacBook Pro 2台，預算每台8萬元"

    print(f"📝 測試需求: {test_request}")
    print("🔄 處理中...")

    try:
        result, tokens = agent.process_purchase_request(test_request)

        print("\n📊 處理結果:")
        print(f"- Token 使用量: {tokens}")
        print(f"- 處理狀態: {'成功' if result.get('generation') else '失敗'}")

        generation = result.get("generation", "")
        if generation:
            print("\n🎯 最終回應:")
            print("-" * 40)
            print(generation)
            print("-" * 40)

            # 檢查是否包含請購單號
            if "請購單號" in generation:
                print("✅ 請購流程完成，成功生成請購單號")
                return True
            else:
                print("⚠️  請購流程完成，但未生成請購單號")
                return False
        else:
            print("❌ 未收到有效回應")
            print(f"完整結果: {result}")
            return False

    except Exception as e:
        print(f"❌ 處理失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = quick_test()
    if success:
        print("\n🎉 快速測試通過！請購系統運作正常")
    else:
        print("\n❌ 快速測試失敗，請檢查系統配置")
