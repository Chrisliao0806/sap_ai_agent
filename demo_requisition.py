"""
採購專員系統 - 使用範例

這個範例展示如何使用新的採購專員審核系統
"""

import os
from requisition_agent import RequisitionAgent, RequisitionAgentConfig


def main():
    """主要示範函數"""
    print("🚀 SAP 採購專員審核系統 - 使用範例")
    print("=" * 50)

    # 檢查環境變數
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  請先設定 OpenAI API Key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return

    # 初始化採購專員 AI Agent
    config = RequisitionAgentConfig(
        api_base_url="http://localhost:7777",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        default_procurement_officer="測試採購專員",
        default_department="採購部",
    )

    agent = RequisitionAgent(config)

    print("💬 開始採購專員對話！（輸入 'quit' 結束）")
    print("📝 您可以說：")
    print("   - 查看請購單")
    print("   - 審核 PR20250107ABCDEF（請購單號）")
    print("   - 確認創建採購單")
    print("   - 強制創建採購單")
    print("   - 確認執行")
    print("-" * 50)

    session_id = "procurement_demo_session"

    try:
        while True:
            # 獲取採購專員輸入
            user_input = input("\n👨‍💼 採購專員: ").strip()

            if user_input.lower() in ["quit", "exit", "退出", "結束"]:
                print("\n👋 感謝使用！再見！")
                break

            if not user_input:
                continue

            # 與採購專員 AI Agent 對話
            print("\n🤖 採購系統正在處理...")
            response = agent.chat(user_input, session_id)

            print(f"\n🤖 採購系統: {response}")

            # 顯示當前狀態
            status = agent.get_session_status(session_id)
            print(f"\n📊 狀態: {status['conversation_state']}")

            # 如果有當前處理的請購單，顯示相關資訊
            if status.get("current_request"):
                current_request = status["current_request"]
                print(f"📋 當前處理請購單: {current_request.get('request_id', 'N/A')}")
                print(f"   產品: {current_request.get('product_name', 'N/A')}")
                print(f"   狀態: {current_request.get('status', 'N/A')}")

    except KeyboardInterrupt:
        print("\n\n👋 程式中斷，再見！")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")


if __name__ == "__main__":
    main()
