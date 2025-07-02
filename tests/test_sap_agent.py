#!/usr/bin/env python3
"""
SAP Agent 測試腳本
展示如何使用 SAP Agent 系統進行對話
"""

import os
import queue
import threading
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sap_agent import SAPAgent, SAPAgentConfig

# 載入環境變數
load_dotenv()


def test_sap_agent():
    """測試 SAP Agent 功能"""

    # 配置 SAP Agent
    config = SAPAgentConfig(
        api_base_url="http://localhost:7777",
        model="gpt-4.1-mini",
        max_tokens=1024,
        temperature=0.3,
        openai_api_key=os.getenv("OPENAI_API_KEY", "your-openai-api-key"),
        openai_base_url="https://api.openai.com/v1",
    )

    # 初始化 SAP Agent
    agent = SAPAgent(config)

    print("🤖 SAP Agent 已啟動！")
    print("📋 可以詢問的問題類型：")
    print("   - 採購歷史查詢：'查詢最近的採購記錄'、'MacBook 的採購歷史'")
    print("   - 庫存查詢：'目前庫存狀況如何'、'低庫存商品有哪些'")
    print("   - 請購單管理：'我要申請採購新設備'、'查詢請購單狀態'")
    print("   - 一般對話：'你好'、'系統功能說明'")
    print("=" * 60)

    # 對話歷史
    chat_history = []

    # 測試案例
    test_questions = [
        "你好，我想了解一下 SAP 系統有什麼功能？",
        "請查詢最近的採購記錄",
        "MacBook 還有多少庫存？",
        "哪些商品庫存不足？",
        "我想申請採購新的設備",
        "查詢所有請購單的狀態",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n🔍 測試 {i}: {question}")
        print("-" * 40)

        try:
            # 呼叫 agent
            response, tokens = agent.chat(question, chat_history)

            print(f"🤖 回應: {response}")
            print(f"📊 Token 使用: {tokens}")

            # 更新對話歷史
            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "assistant", "content": response})

        except Exception as e:
            print(f"❌ 錯誤: {e}")

    print("\n" + "=" * 60)
    print("🎯 自動測試完成！")

    # 進入互動模式
    print("\n🗣️  現在可以開始與 SAP Agent 對話...")
    print("💡 輸入 'quit' 或 'exit' 結束對話")

    while True:
        try:
            user_input = input("\n👤 您: ").strip()

            if user_input.lower() in ["quit", "exit", "結束", "離開"]:
                print("👋 再見！")
                break

            if not user_input:
                continue

            print("🤖 SAP Agent: ", end="", flush=True)

            # 呼叫 agent
            response, tokens = agent.chat(user_input, chat_history)
            print(response)

            # 更新對話歷史
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": response})

        except KeyboardInterrupt:
            print("\n\n👋 對話已中斷，再見！")
            break
        except Exception as e:
            print(f"\n❌ 發生錯誤: {e}")


def test_streaming():
    """測試串流功能"""
    print("\n🚀 測試串流功能...")

    config = SAPAgentConfig(
        api_base_url="http://localhost:7777",
        openai_api_key=os.getenv("OPENAI_API_KEY", "your-openai-api-key"),
    )

    agent = SAPAgent(config)

    # 建立串流 queue
    stream_queue = queue.Queue()
    agent.attach_stream_queue(stream_queue)

    def print_stream():
        """印出串流內容"""
        while True:
            try:
                token = stream_queue.get(timeout=1)
                if token == "[[END]]":
                    break
                print(token, end="", flush=True)
            except queue.Empty:
                continue

    # 啟動串流印出 thread
    stream_thread = threading.Thread(target=print_stream)
    stream_thread.daemon = True
    stream_thread.start()

    print("🔍 測試問題: 查詢目前的庫存狀況")
    print("🤖 串流回應: ", end="", flush=True)

    response, tokens = agent.chat("查詢目前的庫存狀況")

    # 等待串流完成
    stream_thread.join(timeout=10)
    print(f"\n📊 完整回應長度: {len(response)} 字元")


if __name__ == "__main__":
    print("🎯 SAP Agent 測試程式")
    print("請確保：")
    print("1. SAP API 服務器正在運行 (python app.py)")
    print("2. 已設置 OPENAI_API_KEY 環境變數")
    print("3. 已安裝必要的套件")
    print()

    choice = input(
        "選擇測試模式：\n1. 基本測試\n2. 串流測試\n3. 兩者都測試\n請輸入 (1/2/3): "
    ).strip()

    if choice == "1":
        test_sap_agent()
    elif choice == "2":
        test_streaming()
    elif choice == "3":
        test_sap_agent()
        test_streaming()
    else:
        print("❌ 無效選擇，執行基本測試...")
        test_sap_agent()
