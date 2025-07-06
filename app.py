from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid
import os
from datetime import datetime, timedelta
import random

# 導入新的對話式 AI Agent
from purchase_agent import ConversationalPurchaseAgent, PurchaseAgentConfig

app = Flask(__name__)
CORS(app)

# 初始化 AI Agent
agent_config = PurchaseAgentConfig(
    api_base_url="http://localhost:7777",
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    default_requester="系統使用者",
    default_department="IT部門",
)

# 全域 AI Agent 實例
ai_agent = ConversationalPurchaseAgent(agent_config)

# 假數據 - 3C產品採購歷史
PURCHASE_HISTORY = [
    {
        "purchase_id": "PH001",
        "product_name": "MacBook Pro 16吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 10,
        "unit_price": 75000,
        "total_amount": 750000,
        "purchase_date": "2024-12-15",
        "status": "已完成",
        "requester": "張小明",
        "department": "IT部門",
    },
    {
        "purchase_id": "PH001A",
        "product_name": "MacBook Pro 14吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 5,
        "unit_price": 65000,
        "total_amount": 325000,
        "purchase_date": "2024-12-12",
        "status": "已完成",
        "requester": "王小美",
        "department": "設計部門",
    },
    {
        "purchase_id": "PH002",
        "product_name": "iPhone 15 Pro",
        "category": "智慧型手機",
        "supplier": "Apple Inc.",
        "quantity": 25,
        "unit_price": 35000,
        "total_amount": 875000,
        "purchase_date": "2024-12-10",
        "status": "已完成",
        "requester": "李小華",
        "department": "業務部門",
    },
    {
        "purchase_id": "PH003",
        "product_name": "Dell Monitor 27吋 4K",
        "category": "顯示器",
        "supplier": "Dell Technologies",
        "quantity": 15,
        "unit_price": 18000,
        "total_amount": 270000,
        "purchase_date": "2024-12-05",
        "status": "已完成",
        "requester": "王小芳",
        "department": "設計部門",
    },
    {
        "purchase_id": "PH004",
        "product_name": "iPad Pro 12.9吋",
        "category": "平板電腦",
        "supplier": "Apple Inc.",
        "quantity": 8,
        "unit_price": 35000,
        "total_amount": 280000,
        "purchase_date": "2024-11-28",
        "status": "已完成",
        "requester": "陳小強",
        "department": "行銷部門",
    },
    {
        "purchase_id": "PH005",
        "product_name": "Surface Laptop Studio",
        "category": "筆記型電腦",
        "supplier": "Microsoft",
        "quantity": 5,
        "unit_price": 65000,
        "total_amount": 325000,
        "purchase_date": "2024-11-20",
        "status": "已完成",
        "requester": "林小美",
        "department": "研發部門",
    },
    {
        "purchase_id": "PH006",
        "product_name": "MacBook Pro 14吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 1,
        "unit_price": 55000,
        "total_amount": 55000,
        "purchase_date": "2024-10-15",
        "status": "已完成",
        "requester": "廖小魚",
        "department": "IT部門",
    },
    {
        "purchase_id": "PH007",
        "product_name": "MacBook Pro 16吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 2,
        "unit_price": 75000,
        "total_amount": 150000,
        "purchase_date": "2024-12-17",
        "status": "已完成",
        "requester": "王奕翔",
        "department": "IT部門",
    },
    {
        "purchase_id": "PH008",
        "product_name": "Surface Laptop",
        "category": "筆記型電腦",
        "supplier": "Microsoft",
        "quantity": 5,
        "unit_price": 45000,
        "total_amount": 225000,
        "purchase_date": "2024-11-15",
        "status": "已完成",
        "requester": "顧王明",
        "department": "研發部門",
    },
    {
        "purchase_id": "PH009",
        "product_name": "Surface Laptop Studio",
        "category": "筆記型電腦",
        "supplier": "Microsoft",
        "quantity": 10,
        "unit_price": 65000,
        "total_amount": 650000,
        "purchase_date": "2024-09-15",
        "status": "已完成",
        "requester": "張小龍",
        "department": "研發部門",
    },
    # 新增的10筆資料
    {
        "purchase_id": "PH010",
        "product_name": "MacBook Pro 14吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 8,
        "unit_price": 55000,
        "total_amount": 440000,
        "purchase_date": "2024-12-20",
        "status": "已完成",
        "requester": "陳建宏",
        "department": "IT部門",
    },
    {
        "purchase_id": "PH011",
        "product_name": "MacBook Air 13吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 6,
        "unit_price": 40000,
        "total_amount": 240000,
        "purchase_date": "2024-12-18",
        "status": "已完成",
        "requester": "劉志強",
        "department": "研發部門",
    },
    {
        "purchase_id": "PH012",
        "product_name": "Surface Pro 9",
        "category": "平板電腦",
        "supplier": "Microsoft",
        "quantity": 12,
        "unit_price": 38000,
        "total_amount": 456000,
        "purchase_date": "2024-12-12",
        "status": "已完成",
        "requester": "許雅婷",
        "department": "業務部門",
    },
    {
        "purchase_id": "PH013",
        "product_name": "MacBook Pro 16吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 3,
        "unit_price": 75000,
        "total_amount": 225000,
        "purchase_date": "2024-12-08",
        "status": "已完成",
        "requester": "楊承翰",
        "department": "IT部門",
    },
    {
        "purchase_id": "PH014",
        "product_name": "Surface Book 3",
        "category": "筆記型電腦",
        "supplier": "Microsoft",
        "quantity": 4,
        "unit_price": 58000,
        "total_amount": 232000,
        "purchase_date": "2024-12-03",
        "status": "已完成",
        "requester": "黃敏慧",
        "department": "研發部門",
    },
    {
        "purchase_id": "PH015",
        "product_name": "Surface Studio",
        "category": "桌上型電腦",
        "supplier": "Microsoft",
        "quantity": 2,
        "unit_price": 85000,
        "total_amount": 170000,
        "purchase_date": "2024-11-30",
        "status": "已完成",
        "requester": "鄭文傑",
        "department": "設計部門",
    },
    {
        "purchase_id": "PH016",
        "product_name": "MacBook Air 15吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 7,
        "unit_price": 45000,
        "total_amount": 315000,
        "purchase_date": "2024-11-25",
        "status": "已完成",
        "requester": "吳佳穎",
        "department": "研發部門",
    },
    {
        "purchase_id": "PH017",
        "product_name": "Surface Laptop 5",
        "category": "筆記型電腦",
        "supplier": "Microsoft",
        "quantity": 15,
        "unit_price": 42000,
        "total_amount": 630000,
        "purchase_date": "2024-11-18",
        "status": "已完成",
        "requester": "謝志明",
        "department": "業務部門",
    },
    {
        "purchase_id": "PH018",
        "product_name": "MacBook Pro 14吋",
        "category": "筆記型電腦",
        "supplier": "Apple Inc.",
        "quantity": 5,
        "unit_price": 55000,
        "total_amount": 275000,
        "purchase_date": "2024-11-10",
        "status": "已完成",
        "requester": "李志偉",
        "department": "IT部門",
    },
    {
        "purchase_id": "PH019",
        "product_name": "Surface Go 3",
        "category": "平板電腦",
        "supplier": "Microsoft",
        "quantity": 20,
        "unit_price": 25000,
        "total_amount": 500000,
        "purchase_date": "2024-11-05",
        "status": "已完成",
        "requester": "張雅雯",
        "department": "行銷部門",
    },
]

# 假數據 - 庫存資訊
INVENTORY_DATA = [
    {
        "product_id": "INV001",
        "product_name": "MacBook Pro 16吋",
        "category": "筆記型電腦",
        "current_stock": 15,  # 根據採購歷史：10+2+3=15台
        "reserved_stock": 3,
        "available_stock": 12,
        "min_stock_level": 8,
        "max_stock_level": 40,
        "unit_cost": 75000,
        "location": "倉庫A-1",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV002",
        "product_name": "MacBook Pro 14吋",
        "category": "筆記型電腦",
        "current_stock": 14,  # 根據採購歷史：1+8+5=14台
        "reserved_stock": 2,
        "available_stock": 12,
        "min_stock_level": 5,
        "max_stock_level": 30,
        "unit_cost": 55000,
        "location": "倉庫A-1",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV003",
        "product_name": "MacBook Air 13吋",
        "category": "筆記型電腦",
        "current_stock": 6,  # 根據採購歷史：6台
        "reserved_stock": 1,
        "available_stock": 5,
        "min_stock_level": 3,
        "max_stock_level": 20,
        "unit_cost": 40000,
        "location": "倉庫A-2",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV004",
        "product_name": "MacBook Air 15吋",
        "category": "筆記型電腦",
        "current_stock": 7,  # 根據採購歷史：7台
        "reserved_stock": 1,
        "available_stock": 6,
        "min_stock_level": 3,
        "max_stock_level": 20,
        "unit_cost": 45000,
        "location": "倉庫A-2",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV005",
        "product_name": "Surface Laptop Studio",
        "category": "筆記型電腦",
        "current_stock": 15,  # 根據採購歷史：5+10=15台
        "reserved_stock": 2,
        "available_stock": 13,
        "min_stock_level": 5,
        "max_stock_level": 30,
        "unit_cost": 65000,
        "location": "倉庫C-1",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV006",
        "product_name": "Surface Laptop",
        "category": "筆記型電腦",
        "current_stock": 5,  # 根據採購歷史：5台
        "reserved_stock": 1,
        "available_stock": 4,
        "min_stock_level": 3,
        "max_stock_level": 20,
        "unit_cost": 45000,
        "location": "倉庫C-1",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV007",
        "product_name": "Surface Laptop 5",
        "category": "筆記型電腦",
        "current_stock": 15,  # 根據採購歷史：15台
        "reserved_stock": 3,
        "available_stock": 12,
        "min_stock_level": 5,
        "max_stock_level": 30,
        "unit_cost": 42000,
        "location": "倉庫C-1",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV008",
        "product_name": "Surface Book 3",
        "category": "筆記型電腦",
        "current_stock": 4,  # 根據採購歷史：4台
        "reserved_stock": 1,
        "available_stock": 3,
        "min_stock_level": 2,
        "max_stock_level": 15,
        "unit_cost": 58000,
        "location": "倉庫C-2",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV009",
        "product_name": "Surface Studio",
        "category": "桌上型電腦",
        "current_stock": 2,  # 根據採購歷史：2台
        "reserved_stock": 0,
        "available_stock": 2,
        "min_stock_level": 1,
        "max_stock_level": 8,
        "unit_cost": 85000,
        "location": "倉庫C-3",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV010",
        "product_name": "Surface Pro 9",
        "category": "平板電腦",
        "current_stock": 12,  # 根據採購歷史：12台
        "reserved_stock": 2,
        "available_stock": 10,
        "min_stock_level": 5,
        "max_stock_level": 25,
        "unit_cost": 38000,
        "location": "倉庫C-4",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV011",
        "product_name": "Surface Go 3",
        "category": "平板電腦",
        "current_stock": 20,  # 根據採購歷史：20台
        "reserved_stock": 5,
        "available_stock": 15,
        "min_stock_level": 8,
        "max_stock_level": 40,
        "unit_cost": 25000,
        "location": "倉庫C-4",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV012",
        "product_name": "iPhone 15 Pro",
        "category": "智慧型手機",
        "current_stock": 25,  # 根據採購歷史：25台
        "reserved_stock": 5,
        "available_stock": 20,
        "min_stock_level": 10,
        "max_stock_level": 50,
        "unit_cost": 35000,
        "location": "倉庫A-3",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV013",
        "product_name": "iPad Pro 12.9吋",
        "category": "平板電腦",
        "current_stock": 8,  # 根據採購歷史：8台
        "reserved_stock": 1,
        "available_stock": 7,
        "min_stock_level": 3,
        "max_stock_level": 20,
        "unit_cost": 35000,
        "location": "倉庫A-4",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV014",
        "product_name": "Dell Monitor 27吋 4K",
        "category": "顯示器",
        "current_stock": 15,  # 根據採購歷史：15台
        "reserved_stock": 2,
        "available_stock": 13,
        "min_stock_level": 5,
        "max_stock_level": 30,
        "unit_cost": 18000,
        "location": "倉庫B-1",
        "last_updated": "2025-01-15",
    },
]

# 假數據 - 請購單
PURCHASE_REQUESTS = {}


@app.route("/api/chat", methods=["POST"])
def chat_with_agent():
    """與 AI Agent 對話"""
    try:
        data = request.get_json()

        if not data or "message" not in data:
            return jsonify({"status": "error", "message": "請提供對話訊息"}), 400

        user_message = data["message"]
        session_id = data.get("session_id", "default")

        # 呼叫 AI Agent 進行對話
        response = ai_agent.chat(user_message, session_id)

        # 獲取當前會話狀態
        session_status = ai_agent.get_session_status(session_id)

        return jsonify(
            {
                "status": "success",
                "message": "對話處理完成",
                "response": response,
                "session_id": session_id,
                "conversation_state": session_status.get("conversation_state"),
                "has_recommendation": session_status.get("current_recommendation")
                is not None,
                "has_confirmed_order": session_status.get("confirmed_order")
                is not None,
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "message": f"對話處理失敗: {str(e)}"}), 500


@app.route("/api/chat/session/<session_id>", methods=["GET"])
def get_session_status(session_id):
    """獲取會話狀態"""
    try:
        session_status = ai_agent.get_session_status(session_id)

        return jsonify(
            {
                "status": "success",
                "message": "成功獲取會話狀態",
                "session_id": session_id,
                "data": session_status,
            }
        )

    except Exception as e:
        return jsonify(
            {"status": "error", "message": f"獲取會話狀態失敗: {str(e)}"}
        ), 500


@app.route("/api/chat/session/<session_id>", methods=["DELETE"])
def reset_session(session_id):
    """重置會話狀態"""
    try:
        ai_agent.reset_session(session_id)

        return jsonify(
            {
                "status": "success",
                "message": f"會話 {session_id} 已重置",
                "session_id": session_id,
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "message": f"重置會話失敗: {str(e)}"}), 500


@app.route("/api/chat/sessions", methods=["GET"])
def get_all_sessions():
    """獲取所有會話列表"""
    try:
        # 獲取所有會話 ID（從 AI Agent 的內部狀態）
        session_ids = list(ai_agent._session_states.keys())

        sessions_info = []
        for session_id in session_ids:
            session_status = ai_agent.get_session_status(session_id)
            sessions_info.append(
                {
                    "session_id": session_id,
                    "conversation_state": session_status.get("conversation_state"),
                    "last_request": session_status.get("user_request", ""),
                    "chat_count": len(session_status.get("chat_history", [])),
                    "has_recommendation": session_status.get("current_recommendation")
                    is not None,
                    "has_confirmed_order": session_status.get("confirmed_order")
                    is not None,
                }
            )

        return jsonify(
            {
                "status": "success",
                "message": "成功獲取所有會話",
                "total_sessions": len(sessions_info),
                "data": sessions_info,
            }
        )

    except Exception as e:
        return jsonify(
            {"status": "error", "message": f"獲取會話列表失敗: {str(e)}"}
        ), 500


@app.route("/", methods=["GET"])
def home():
    """API 首頁"""
    return jsonify(
        {
            "message": "歡迎使用 SAP 對話式請購系統",
            "version": "2.0.0",
            "features": [
                "智能對話式請購",
                "自動產品推薦",
                "採購歷史分析",
                "庫存資訊查詢",
                "請購單管理",
            ],
            "available_endpoints": {
                "對話式請購": "/api/chat (POST)",
                "會話狀態": "/api/chat/session/<session_id> (GET)",
                "重置會話": "/api/chat/session/<session_id> (DELETE)",
                "所有會話": "/api/chat/sessions (GET)",
                "採購歷史": "/api/purchase-history",
                "採購歷史詳細資訊": "/api/purchase-history/<purchase_id>",
                "庫存資訊": "/api/inventory",
                "特定產品庫存": "/api/inventory/<product_id>",
                "創建請購單": "/api/purchase-request (POST)",
                "查詢請購單": "/api/purchase-request/<request_id>",
                "所有請購單": "/api/purchase-requests",
            },
            "usage_examples": {
                "開始對話": {
                    "method": "POST",
                    "url": "/api/chat",
                    "body": {
                        "message": "我需要採購一台筆記型電腦",
                        "session_id": "user123",
                    },
                },
                "查看會話狀態": {"method": "GET", "url": "/api/chat/session/user123"},
            },
        }
    )


@app.route("/api/purchase-history", methods=["GET"])
def get_purchase_history():
    """取得3C產品採購歷史"""
    # 支援查詢參數
    category = request.args.get("category")
    supplier = request.args.get("supplier")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    filtered_history = PURCHASE_HISTORY.copy()

    # 根據類別篩選
    if category:
        filtered_history = [
            h for h in filtered_history if category.lower() in h["category"].lower()
        ]

    # 根據供應商篩選
    if supplier:
        filtered_history = [
            h for h in filtered_history if supplier.lower() in h["supplier"].lower()
        ]

    # 根據日期篩選
    if start_date:
        filtered_history = [
            h for h in filtered_history if h["purchase_date"] >= start_date
        ]

    if end_date:
        filtered_history = [
            h for h in filtered_history if h["purchase_date"] <= end_date
        ]

    return jsonify(
        {
            "status": "success",
            "message": "成功取得採購歷史",
            "total_records": len(filtered_history),
            "data": filtered_history,
        }
    )


@app.route("/api/purchase-history/<purchase_id>", methods=["GET"])
def get_purchase_detail(purchase_id):
    """取得特定採購的詳細資訊"""
    purchase = next(
        (p for p in PURCHASE_HISTORY if p["purchase_id"] == purchase_id), None
    )

    if not purchase:
        return jsonify(
            {"status": "error", "message": f"找不到採購單號 {purchase_id}"}
        ), 404

    # 添加更詳細的資訊
    detailed_purchase = purchase.copy()
    detailed_purchase.update(
        {
            "delivery_address": "台北市信義區信義路五段7號",
            "payment_terms": "30天付款",
            "delivery_status": "已送達",
            "invoice_number": f"INV-{purchase_id}",
            "approval_chain": [
                {"approver": "直屬主管", "status": "已批准", "date": "2024-12-01"},
                {"approver": "部門經理", "status": "已批准", "date": "2024-12-02"},
                {"approver": "財務部門", "status": "已批准", "date": "2024-12-03"},
            ],
        }
    )

    return jsonify(
        {
            "status": "success",
            "message": "成功取得採購詳細資訊",
            "data": detailed_purchase,
        }
    )


@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    """取得3C產品庫存資訊"""
    # 支援查詢參數
    category = request.args.get("category")
    low_stock = request.args.get("low_stock", "").lower() == "true"
    location = request.args.get("location")

    filtered_inventory = INVENTORY_DATA.copy()

    # 根據類別篩選
    if category:
        filtered_inventory = [
            i for i in filtered_inventory if category.lower() in i["category"].lower()
        ]

    # 篩選低庫存商品
    if low_stock:
        filtered_inventory = [
            i
            for i in filtered_inventory
            if i["available_stock"] <= i["min_stock_level"]
        ]

    # 根據倉庫位置篩選
    if location:
        filtered_inventory = [
            i for i in filtered_inventory if location.lower() in i["location"].lower()
        ]

    # 計算總庫存價值
    total_value = sum(
        item["current_stock"] * item["unit_cost"] for item in filtered_inventory
    )

    return jsonify(
        {
            "status": "success",
            "message": "成功取得庫存資訊",
            "total_items": len(filtered_inventory),
            "total_inventory_value": total_value,
            "data": filtered_inventory,
        }
    )


@app.route("/api/inventory/<product_id>", methods=["GET"])
def get_product_inventory(product_id):
    """取得特定產品的庫存資訊"""
    product = next((p for p in INVENTORY_DATA if p["product_id"] == product_id), None)

    if not product:
        return jsonify({"status": "error", "message": f"找不到產品 {product_id}"}), 404

    # 添加庫存狀態分析
    inventory_status = "正常"
    if product["available_stock"] <= product["min_stock_level"]:
        inventory_status = "庫存不足"
    elif product["available_stock"] >= product["max_stock_level"]:
        inventory_status = "庫存過多"

    detailed_product = product.copy()
    detailed_product.update(
        {
            "inventory_status": inventory_status,
            "reorder_suggestion": product["available_stock"]
            <= product["min_stock_level"],
            "stock_turnover_days": random.randint(15, 45),
            "supplier_lead_time": f"{random.randint(3, 14)}天",
        }
    )

    return jsonify(
        {
            "status": "success",
            "message": "成功取得產品庫存資訊",
            "data": detailed_product,
        }
    )


@app.route("/api/purchase-request", methods=["POST"])
def create_purchase_request():
    """創建請購單"""
    try:
        data = request.get_json()

        # 驗證必要欄位
        required_fields = [
            "product_name",
            "quantity",
            "unit_price",
            "requester",
            "department",
        ]
        for field in required_fields:
            if field not in data:
                return jsonify(
                    {"status": "error", "message": f"缺少必要欄位: {field}"}
                ), 400

        # 生成請購單ID
        request_id = (
            f"PR{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
        )

        # 創建請購單
        purchase_request = {
            "request_id": request_id,
            "product_name": data["product_name"],
            "category": data.get("category", "3C產品"),
            "quantity": data["quantity"],
            "unit_price": data["unit_price"],
            "total_amount": data["quantity"] * data["unit_price"],
            "requester": data["requester"],
            "department": data["department"],
            "reason": data.get("reason", ""),
            "urgent": data.get("urgent", False),
            "expected_delivery_date": data.get("expected_delivery_date", ""),
            "status": "待審核",
            "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "approval_status": "pending",
            "current_approver": "直屬主管",
            "tracking_number": f"TRK-{request_id}",
        }

        # 儲存請購單
        PURCHASE_REQUESTS[request_id] = purchase_request

        return jsonify(
            {
                "status": "success",
                "message": "請購單創建成功",
                "request_id": request_id,
                "data": purchase_request,
            }
        ), 201

    except Exception as e:
        return jsonify({"status": "error", "message": f"創建請購單失敗: {str(e)}"}), 500


@app.route("/api/purchase-request/<request_id>", methods=["GET"])
def get_purchase_request(request_id):
    """查詢特定請購單狀態"""
    if request_id not in PURCHASE_REQUESTS:
        return jsonify(
            {"status": "error", "message": f"找不到請購單 {request_id}"}
        ), 404

    purchase_request = PURCHASE_REQUESTS[request_id].copy()

    # 模擬審核進度
    statuses = ["待審核", "審核中", "已批准", "採購中", "已完成", "已拒絕"]
    if purchase_request["status"] == "待審核":
        # 隨機更新狀態（模擬系統運作）
        if random.random() > 0.5:
            purchase_request["status"] = random.choice(statuses[1:4])
            if purchase_request["status"] == "已批准":
                purchase_request["approval_date"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            elif purchase_request["status"] == "已拒絕":
                purchase_request["rejection_reason"] = "預算不足"

    # 添加審核軌跡
    purchase_request["approval_trail"] = [
        {
            "step": 1,
            "approver": "直屬主管",
            "status": "已批准" if purchase_request["status"] != "待審核" else "待審核",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if purchase_request["status"] != "待審核"
            else None,
            "comment": "符合部門需求",
        },
        {
            "step": 2,
            "approver": "部門經理",
            "status": "已批准"
            if purchase_request["status"] in ["已批准", "採購中", "已完成"]
            else "待審核",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if purchase_request["status"] in ["已批准", "採購中", "已完成"]
            else None,
            "comment": "預算範圍內，同意採購",
        },
        {
            "step": 3,
            "approver": "財務部門",
            "status": "已批准"
            if purchase_request["status"] in ["已批准", "採購中", "已完成"]
            else "待審核",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if purchase_request["status"] in ["已批准", "採購中", "已完成"]
            else None,
            "comment": "財務審核通過",
        },
    ]

    return jsonify(
        {"status": "success", "message": "成功取得請購單資訊", "data": purchase_request}
    )


@app.route("/api/purchase-requests", methods=["GET"])
def get_all_purchase_requests():
    """取得所有請購單"""
    # 支援查詢參數
    requester = request.args.get("requester")
    department = request.args.get("department")
    status = request.args.get("status")

    filtered_requests = list(PURCHASE_REQUESTS.values())

    # 根據申請人篩選
    if requester:
        filtered_requests = [
            r for r in filtered_requests if requester.lower() in r["requester"].lower()
        ]

    # 根據部門篩選
    if department:
        filtered_requests = [
            r
            for r in filtered_requests
            if department.lower() in r["department"].lower()
        ]

    # 根據狀態篩選
    if status:
        filtered_requests = [
            r for r in filtered_requests if status.lower() in r["status"].lower()
        ]

    return jsonify(
        {
            "status": "success",
            "message": "成功取得所有請購單",
            "total_requests": len(filtered_requests),
            "data": filtered_requests,
        }
    )


if __name__ == "__main__":
    print("🚀 假 SAP API 系統啟動中...")
    print("📝 API 文檔:")
    print("   - 採購歷史: GET /api/purchase-history")
    print("   - 採購詳細: GET /api/purchase-history/<purchase_id>")
    print("   - 庫存資訊: GET /api/inventory")
    print("   - 產品庫存: GET /api/inventory/<product_id>")
    print("   - 創建請購: POST /api/purchase-request")
    print("   - 查詢請購: GET /api/purchase-request/<request_id>")
    print("   - 所有請購: GET /api/purchase-requests")
    print("🌐 伺服器啟動在: http://localhost:7777")
    app.run(debug=True, host="0.0.0.0", port=7777)
