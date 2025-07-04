"""
對話式請購系統 - 使用範例

這個範例展示如何使用新的對話式請購系統
"""

import os
from purchase_agent import ConversationalPurchaseAgent, PurchaseAgentConfig


def main():
    """主要示範函數"""
    print("🚀 SAP 對話式請購系統 - 使用範例")
    print("=" * 50)

    # 檢查環境變數
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  請先設定 OpenAI API Key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return

    # 初始化 AI Agent
    config = PurchaseAgentConfig(
        api_base_url="http://localhost:7777",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        default_requester="測試使用者",
        default_department="IT部門",
    )

    agent = ConversationalPurchaseAgent(config)

    print("💬 開始對話！（輸入 'quit' 結束）")
    print("📝 您可以說：")
    print("   - 我需要採購一台筆記型電腦")
    print("   - 我要買平板電腦，預算3萬元")
    print("   - 我需要手機用於業務")
    print("-" * 50)

    session_id = "demo_session"

    try:
        while True:
            # 獲取使用者輸入
            user_input = input("\n👤 您: ").strip()

            if user_input.lower() in ["quit", "exit", "退出", "結束"]:
                print("\n👋 感謝使用！再見！")
                break

            if not user_input:
                continue

            # 與 AI Agent 對話
            print("\n🤖 AI助手正在處理...")
            response = agent.chat(user_input, session_id)

            print(f"\n🤖 AI助手: {response}")

            # 顯示當前狀態
            status = agent.get_session_status(session_id)
            print(f"\n📊 狀態: {status['conversation_state']}")

    except KeyboardInterrupt:
        print("\n\n👋 程式中斷，再見！")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")


if __name__ == "__main__":
    main()
