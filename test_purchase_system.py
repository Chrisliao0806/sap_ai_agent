"""
請購系統測試腳本

這個腳本提供互動式的請購系統測試功能，包括：
1. 基本請購流程測試
2. 串流回應測試
3. 多輪對話測試
4. 錯誤處理測試
"""

import os
import queue
import threading
import time
from typing import Dict, List
from dotenv import load_dotenv

from purchase_agent import PurchaseAgent, PurchaseAgentConfig

# 載入環境變數
load_dotenv()


class PurchaseSystemTester:
    """請購系統測試器"""

    def __init__(self):
        self.config = PurchaseAgentConfig(
            api_base_url="http://localhost:7777",
            model="gpt-4o-mini",
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.agent = PurchaseAgent(self.config)
        self.chat_history = []

    def test_basic_purchase_flow(self):
        """測試基本請購流程"""
        print("🎯 測試基本請購流程")
        print("=" * 60)

        # 測試案例
        test_cases = [
            "我需要申請採購新的軟體開發工程師筆記型電腦，規格要求：MacBook Pro，記憶體16GB以上，需要5台，預算每台不超過8萬元。",
            "我們設計部門需要購買新的顯示器，要求4K解析度，27吋以上，需要10台，預算控制在每台2萬元以內。",
            "行銷部門需要iPad進行展示，要求Pro版本，12.9吋螢幕，需要3台，希望能盡快交貨。",
            "IT部門需要擴充伺服器設備，需要Surface Studio作為開發機，要求高效能配置，需要2台。",
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📋 測試案例 {i}:")
            print(f"請購需求: {test_case}")
            print("-" * 40)

            try:
                result, tokens = self.agent.process_purchase_request(test_case, self.chat_history)

                print(f"✅ 測試完成")
                print(f"📊 Token 使用量: {tokens}")

                # 顯示完整的最終結果
                generation = result.get('generation', '無回應')
                if generation:
                    print(f"🎯 最終結果:")
                    print("-" * 60)
                    print(generation)
                    print("-" * 60)
                else:
                    print(f"⚠️  未收到有效回應")
                    print(f"📋 完整結果: {result}")

                # 更新對話歷史
                self.chat_history.append({
                    "role": "user",
                    "content": test_case
                })
                self.chat_history.append({
                    "role": "assistant", 
                    "content": generation
                })

            except Exception as e:
                print(f"❌ 測試失敗: {e}")
                import traceback
                traceback.print_exc()

            print("\n" + "=" * 60)
            time.sleep(2)  # 避免API過快呼叫

    def test_streaming_response(self):
        """測試串流回應"""
        print("⚡ 測試串流回應")
        print("=" * 60)

        # 設定串流佇列
        stream_queue = queue.Queue()
        self.agent.attach_stream_queue(stream_queue)

        # 測試請購需求
        test_request = (
            "我需要為新進員工採購辦公設備，包括筆記型電腦和顯示器，需要考慮成本效益。"
        )

        print(f"📝 請購需求: {test_request}")
        print("🔄 開始串流回應...")
        print("-" * 40)

        def stream_handler():
            """處理串流輸出"""
            while True:
                try:
                    token = stream_queue.get(timeout=1)
                    if token == "[[END]]":
                        break
                    print(token, end="", flush=True)
                except queue.Empty:
                    continue

        # 啟動串流處理線程
        stream_thread = threading.Thread(target=stream_handler)
        stream_thread.daemon = True
        stream_thread.start()

        # 處理請購
        result, tokens = self.agent.process_purchase_request(
            test_request, self.chat_history
        )

        # 等待串流完成
        stream_thread.join(timeout=5)

        print(f"\n\n📊 Token 使用量: {tokens}")
        print("✅ 串流測試完成")

    def test_interactive_mode(self):
        """互動模式測試"""
        print("🎮 互動模式測試")
        print("=" * 60)
        print("請輸入您的請購需求（輸入 'exit' 結束）:")

        while True:
            try:
                user_input = input("\n👤 您的請購需求: ").strip()

                if user_input.lower() in ["exit", "quit", "結束"]:
                    print("👋 感謝使用請購系統！")
                    break

                if not user_input:
                    print("❌ 請輸入有效的請購需求")
                    continue

                print("🤖 AI處理中...")
                print("-" * 40)

                # 設定串流
                stream_queue = queue.Queue()
                self.agent.attach_stream_queue(stream_queue)

                def stream_handler():
                    while True:
                        try:
                            token = stream_queue.get(timeout=1)
                            if token == "[[END]]":
                                break
                            print(token, end="", flush=True)
                        except queue.Empty:
                            continue

                # 啟動串流處理
                stream_thread = threading.Thread(target=stream_handler)
                stream_thread.daemon = True
                stream_thread.start()

                # 處理請購
                result, tokens = self.agent.process_purchase_request(
                    user_input, self.chat_history
                )

                # 等待串流完成
                stream_thread.join(timeout=10)

                # 更新對話歷史
                self.chat_history.append({"role": "user", "content": user_input})
                self.chat_history.append(
                    {"role": "assistant", "content": result.get("generation", "")}
                )

                print(f"\n📊 Token 使用量: {tokens}")

            except KeyboardInterrupt:
                print("\n👋 感謝使用請購系統！")
                break
            except Exception as e:
                print(f"❌ 處理錯誤: {e}")

    def test_error_handling(self):
        """測試錯誤處理"""
        print("🔧 測試錯誤處理")
        print("=" * 60)

        # 測試無效的API URL
        print("📍 測試無效的API URL...")
        invalid_config = PurchaseAgentConfig(
            api_base_url="http://invalid-url:9999",
            model="gpt-4o-mini",
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        )

        invalid_agent = PurchaseAgent(invalid_config)

        try:
            result, tokens = invalid_agent.process_purchase_request(
                "測試無效API", self.chat_history
            )
            print(f"結果: {result.get('generation', 'N/A')[:100]}...")
        except Exception as e:
            print(f"❌ 預期錯誤: {e}")

        # 測試空請求
        print("\n📍 測試空請求...")
        try:
            result, tokens = self.agent.process_purchase_request("", self.chat_history)
            print(f"結果: {result.get('generation', 'N/A')[:100]}...")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

        print("✅ 錯誤處理測試完成")

    def run_all_tests(self):
        """執行所有測試"""
        print("🚀 請購系統全面測試")
        print("=" * 80)

        # 檢查環境
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ 請設定 OPENAI_API_KEY 環境變數")
            return

        print("✅ 環境檢查通過")
        print(f"🔑 API Key: {os.getenv('OPENAI_API_KEY')[:10]}...")
        print(f"🌐 API Base URL: {self.config.api_base_url}")
        print(f"🤖 Model: {self.config.model}")

        # 檢查API連線
        try:
            import requests

            response = requests.get(f"{self.config.api_base_url}/", timeout=5)
            if response.status_code == 200:
                print("✅ SAP API 連線正常")
            else:
                print(f"⚠️ SAP API 回應異常: {response.status_code}")
        except Exception as e:
            print(f"❌ SAP API 連線失敗: {e}")
            print("請確認 API 服務器是否正在運行 (python app.py)")
            return

        print("\n" + "=" * 80)

        # 執行測試
        tests = [
            ("基本功能測試", self.test_basic_purchase_flow),
            ("串流回應測試", self.test_streaming_response),
            ("錯誤處理測試", self.test_error_handling),
        ]

        for test_name, test_func in tests:
            print(f"\n🎯 開始 {test_name}...")
            try:
                test_func()
                print(f"✅ {test_name} 完成")
            except Exception as e:
                print(f"❌ {test_name} 失敗: {e}")

            print("\n" + "=" * 80)
            time.sleep(2)

        print("🎉 所有測試完成！")


def main():
    """主程式"""
    print("🎯 SAP 請購系統測試程式")
    print("=" * 50)

    # 檢查前置條件
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ 請設定 OPENAI_API_KEY 環境變數")
        print("範例: export OPENAI_API_KEY='your-api-key-here'")
        return

    print("請確保：")
    print("1. SAP API 服務器正在運行 (python app.py)")
    print("2. 已設置 OPENAI_API_KEY 環境變數")
    print("3. 已安裝必要的套件")
    print()

    # 選擇測試模式
    tester = PurchaseSystemTester()

    while True:
        print("選擇測試模式：")
        print("1. 基本功能測試")
        print("2. 串流回應測試")
        print("3. 互動模式")
        print("4. 錯誤處理測試")
        print("5. 完整測試")
        print("6. 結束")

        choice = input("\n請輸入選擇 (1-6): ").strip()

        if choice == "1":
            tester.test_basic_purchase_flow()
        elif choice == "2":
            tester.test_streaming_response()
        elif choice == "3":
            tester.test_interactive_mode()
        elif choice == "4":
            tester.test_error_handling()
        elif choice == "5":
            tester.run_all_tests()
        elif choice == "6":
            print("👋 感謝使用！")
            break
        else:
            print("❌ 無效選擇，請重新輸入")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
