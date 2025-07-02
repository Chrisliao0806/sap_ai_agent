from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid
from datetime import datetime, timedelta
import random

app = Flask(__name__)
CORS(app)

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
]

# 假數據 - 庫存資訊
INVENTORY_DATA = [
    {
        "product_id": "INV001",
        "product_name": "MacBook Pro 16吋",
        "category": "筆記型電腦",
        "current_stock": 25,
        "reserved_stock": 5,
        "available_stock": 20,
        "min_stock_level": 10,
        "max_stock_level": 50,
        "unit_cost": 75000,
        "location": "倉庫A-1",
        "last_updated": "2025-01-15",
    },
    {
        "product_id": "INV002",
        "product_name": "iPhone 15 Pro",
        "category": "智慧型手機",
        "current_stock": 45,
        "reserved_stock": 8,
        "available_stock": 37,
        "min_stock_level": 20,
        "max_stock_level": 80,
        "unit_cost": 35000,
        "location": "倉庫A-2",
        "last_updated": "2025-01-14",
    },
    {
        "product_id": "INV003",
        "product_name": "Dell Monitor 27吋 4K",
        "category": "顯示器",
        "current_stock": 32,
        "reserved_stock": 3,
        "available_stock": 29,
        "min_stock_level": 15,
        "max_stock_level": 60,
        "unit_cost": 18000,
        "location": "倉庫B-1",
        "last_updated": "2025-01-13",
    },
    {
        "product_id": "INV004",
        "product_name": "iPad Pro 12.9吋",
        "category": "平板電腦",
        "current_stock": 18,
        "reserved_stock": 2,
        "available_stock": 16,
        "min_stock_level": 8,
        "max_stock_level": 40,
        "unit_cost": 35000,
        "location": "倉庫A-3",
        "last_updated": "2025-01-12",
    },
    {
        "product_id": "INV005",
        "product_name": "Surface Laptop Studio",
        "category": "筆記型電腦",
        "current_stock": 12,
        "reserved_stock": 1,
        "available_stock": 11,
        "min_stock_level": 5,
        "max_stock_level": 25,
        "unit_cost": 65000,
        "location": "倉庫C-1",
        "last_updated": "2025-01-11",
    },
]

# 假數據 - 請購單
PURCHASE_REQUESTS = {}


@app.route("/", methods=["GET"])
def home():
    """API 首頁"""
    return jsonify(
        {
            "message": "歡迎使用假 SAP API 系統",
            "version": "1.0.0",
            "available_endpoints": {
                "採購歷史": "/api/purchase-history",
                "採購歷史詳細資訊": "/api/purchase-history/<purchase_id>",
                "庫存資訊": "/api/inventory",
                "特定產品庫存": "/api/inventory/<product_id>",
                "創建請購單": "/api/purchase-request (POST)",
                "查詢請購單": "/api/purchase-request/<request_id>",
                "所有請購單": "/api/purchase-requests",
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
