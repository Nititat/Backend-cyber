from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import requests
import json
import bcrypt
from datetime import datetime, timedelta
from collections import Counter
app = Flask(__name__)
CORS(app)
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity

from datetime import datetime, timedelta
# เวลาปัจจุบันใน UTC
now = datetime.utcnow()

# คำนวณเที่ยงคืนของวันก่อนหน้า ("now-1d/d")
yesterday_midnight = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access environment variables
ES_URL = os.getenv("ES_URL")
ES_URL2 = os.getenv("ES_URL2")
ES_USERNAME = os.getenv("ES_USERNAME")
ES_PASSWORD = os.getenv("ES_PASSWORD")

# JWT Configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your_secret_key")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)  # Access Token หมดอายุใน 15 นาที
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)

jwt = JWTManager(app)



import asyncpg

async def connect_to_db():
    return await asyncpg.connect(
        user="postgres",
        password="11223344",
        database="production_db",
        host="localhost"
    )




@app.route("/api/login", methods=["POST"])
def login():
    """
    Login เพื่อรับ JWT Token
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # ตรวจสอบ Username และ Password (ใน Production ควรเข้ารหัส Password)
    if username == os.getenv("ADMIN_USER") and password == os.getenv("ADMIN_PASS"):
        access_token = create_access_token(identity=username)
        refresh_token = create_refresh_token(identity=username)

        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token
        }), 200

    return jsonify({"msg": "Invalid username or password"}), 401






@app.route("/api/refresh", methods=["POST"])
@jwt_required(refresh=True)  # Require JWT Refresh Token
def refresh():
    """
    ใช้ Refresh Token เพื่อรับ Access Token ใหม่
    """
    current_user = get_jwt_identity()  # ดึงข้อมูลผู้ใช้งานจาก JWT
    new_access_token = create_access_token(identity=current_user)
    return jsonify({"access_token": new_access_token}), 200



@app.route("/api/alerts", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_alerts():
    """
    ดึงข้อมูล Alerts จาก Elasticsearch
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        # Elasticsearch Query
        query = {
            "query": {
                "term": {
                    "rule.groups": "attack"
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        # ส่งข้อมูลกลับในรูปแบบ JSON
        return jsonify(hits), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching alerts: {e}"}), 500





@app.route("/api/top-mitre-techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_mitre_techniques():
    """
    Fetch Top 10 MITRE ATT&CK Techniques
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        # Elasticsearch Query (from your provided JSON)
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 10
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "script_fields": {},
            "docvalue_fields": [
                {"field": "data.aws.createdAt", "format": "date_time"},
                {"field": "data.aws.end", "format": "date_time"},
                {"field": "data.aws.resource.instanceDetails.launchTime", "format": "date_time"},
                {"field": "data.aws.service.eventFirstSeen", "format": "date_time"},
                {"field": "data.aws.service.eventLastSeen", "format": "date_time"},
                {"field": "data.aws.start", "format": "date_time"},
                {"field": "data.aws.updatedAt", "format": "date_time"},
                {"field": "data.ms-graph.createdDateTime", "format": "date_time"},
                {"field": "data.ms-graph.firstActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastUpdateDateTime", "format": "date_time"},
                {"field": "data.ms-graph.resolvedDateTime", "format": "date_time"},
                {"field": "data.timestamp", "format": "date_time"},
                {"field": "data.vulnerability.published", "format": "date_time"},
                {"field": "data.vulnerability.updated", "format": "date_time"},
                {"field": "syscheck.mtime_after", "format": "date_time"},
                {"field": "syscheck.mtime_before", "format": "date_time"},
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {"match_phrase": {"cluster.name": {"query": "wazuh"}}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now-200d/d",
                                    "lte": "now",   #ถึงเวลาปัจจุบัน
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ],
                    "should": [],
                    "must_not": []
                }
            }
        }

        # Send Elasticsearch request
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # Disable SSL verification (for development only)
        )

        # Raise an exception if the request fails
        response.raise_for_status()

        # Extract the response data
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # Format the results
        results = [{"technique": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching data from Elasticsearch: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/api/top-agents", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_agents():
    """
    ดึงข้อมูล Top 5 Agent Names ที่มีการโจมตีมากที่สุด
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "agent.name",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 5
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "docvalue_fields": [
                {"field": "data.aws.createdAt", "format": "date_time"},
                {"field": "data.aws.end", "format": "date_time"},
                {"field": "data.aws.resource.instanceDetails.launchTime", "format": "date_time"},
                {"field": "data.aws.service.eventFirstSeen", "format": "date_time"},
                {"field": "data.aws.service.eventLastSeen", "format": "date_time"},
                {"field": "data.aws.start", "format": "date_time"},
                {"field": "data.aws.updatedAt", "format": "date_time"},
                {"field": "data.ms-graph.createdDateTime", "format": "date_time"},
                {"field": "data.ms-graph.firstActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastUpdateDateTime", "format": "date_time"},
                {"field": "data.ms-graph.resolvedDateTime", "format": "date_time"},
                {"field": "data.timestamp", "format": "date_time"},
                {"field": "data.vulnerability.published", "format": "date_time"},
                {"field": "data.vulnerability.updated", "format": "date_time"},
                {"field": "syscheck.mtime_after", "format": "date_time"},
                {"field": "syscheck.mtime_before", "format": "date_time"},
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {"match_phrase": {"cluster.name": {"query": "wazuh"}}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now-200d/d",
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ],
                    "should": [],
                    "must_not": []
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลสำหรับการตอบกลับ
        results = [{"agent_name": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top agents: {e}"}), 500






@app.route("/api/top-countries", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_countries():
    """
    ดึงข้อมูล 10 ประเทศที่มีการโจมตีมากที่สุด
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "GeoLocation.country_name",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 10
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "script_fields": {},
            "docvalue_fields": [
                {"field": "data.aws.createdAt", "format": "date_time"},
                {"field": "data.aws.end", "format": "date_time"},
                {"field": "data.aws.resource.instanceDetails.launchTime", "format": "date_time"},
                {"field": "data.aws.service.eventFirstSeen", "format": "date_time"},
                {"field": "data.aws.service.eventLastSeen", "format": "date_time"},
                {"field": "data.aws.start", "format": "date_time"},
                {"field": "data.aws.updatedAt", "format": "date_time"},
                {"field": "data.ms-graph.createdDateTime", "format": "date_time"},
                {"field": "data.ms-graph.firstActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastActivityDateTime", "format": "date_time"},
                {"field": "data.ms-graph.lastUpdateDateTime", "format": "date_time"},
                {"field": "data.ms-graph.resolvedDateTime", "format": "date_time"},
                {"field": "data.timestamp", "format": "date_time"},
                {"field": "data.vulnerability.published", "format": "date_time"},
                {"field": "data.vulnerability.updated", "format": "date_time"},
                {"field": "syscheck.mtime_after", "format": "date_time"},
                {"field": "syscheck.mtime_before", "format": "date_time"},
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now-200d/d",
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลสำหรับการตอบกลับ
        results = [{"country": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top countries: {e}"}), 500




@app.route("/api/top-techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_techniques():
    """
    Fetches the top MITRE techniques with historical attack data broken down by 30-minute intervals.
    """
    try:
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        # Elasticsearch Query for top MITRE techniques within a specific date range
        query = {
            "aggs": {
                "3": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 5
                    },
                    "aggs": {
                        "2": {
                            "date_histogram": {
                                "field": "timestamp",
                                "fixed_interval": "30m",  # 30-minute intervals
                                "time_zone": "Asia/Bangkok",  # Adjust to local timezone
                                "min_doc_count": 1
                            }
                        }
                    }
                }
            },
            "size": 0,  # We only want aggregation results, no hits
            "query": {
                "bool": {
                    "filter": [
                        {"match_all": {}},
                        {"match_phrase": {"cluster.name": {"query": "wazuh"}}},  # Only data from 'wazuh' cluster
                        {"exists": {"field": "rule.mitre.id"}},  # Only documents with a MITRE ID
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now-7d/d",
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # Send the request to Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # Disable SSL verification if using self-signed certificates
        )

        # Check if the request was successful
        response.raise_for_status()

        # Parse the response JSON
        data = response.json()
        techniques_buckets = data.get("aggregations", {}).get("3", {}).get("buckets", [])

        # Prepare results for the response
        results = []
        for technique_bucket in techniques_buckets:
            technique_name = technique_bucket["key"]
            technique_data = {
                "technique": technique_name,
                "histogram": []
            }

            # For each 30-minute interval, get the count of events for the technique
            for interval_bucket in technique_bucket.get("2", {}).get("buckets", []):
                technique_data["histogram"].append({
                    "timestamp": interval_bucket["key_as_string"],  # Timestamp of the 30-minute interval
                    "count": interval_bucket["doc_count"]  # Number of events in this interval
                })

            results.append(technique_data)

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top techniques: {e}"}), 500






@app.route("/api/peak-attack-periods", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_peak_attack_periods():
    """
    ดึงข้อมูลช่วงเวลาที่มีการโจมตีมากที่สุดใน 7 วัน
    """
    try:
        # Elasticsearch Query
        # ดึงข้อมูล User จาก JWT
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        query = {
            "aggs": {
                "2": {
                    "date_histogram": {
                        "field": "timestamp",
                        "fixed_interval": "1h",  # แบ่งข้อมูลตามช่วงเวลา 1 ชั่วโมง
                        "time_zone": "Asia/Bangkok",  # ใช้ timezone ของประเทศไทย
                        "min_doc_count": 1
                    }
                }
            },
            "size": 0,  # ไม่ดึงข้อมูล hits, ดึงเฉพาะ aggregation
            "query": {
                "bool": {
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now-d/d",
                                    "lte": "now",
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # ปิด SSL verification (หากใช้ self-signed certificate)
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลเพื่อเตรียมการตอบกลับ
        results = [{"timestamp": bucket["key_as_string"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching peak attack periods: {e}"}), 500




@app.route('/api/vulnerabilities', methods=['GET'])
@jwt_required()  # Require JWT authentication
def get_vulnerabilities():
    current_user = get_jwt_identity()
    print(f"Request made by: {current_user}")
    """
    ดึงข้อมูล vulnerability severity จาก Elasticsearch โดยใช้โครงสร้าง JSON Query ที่ระบุ
    """
    # Elasticsearch Query
    query = {
        "aggs": {
            "2": {
                "filters": {
                    "filters": {
                        "Critical": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "Critical"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        },
                        "High": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "High"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        },
                        "Medium": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "Medium"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        },
                        "Low": {
                            "bool": {
                                "must": [],
                                "filter": [
                                    {
                                        "bool": {
                                            "should": [
                                                {
                                                    "match_phrase": {
                                                        "vulnerability.severity": "Low"
                                                    }
                                                }
                                            ],
                                            "minimum_should_match": 1
                                        }
                                    }
                                ],
                                "should": [],
                                "must_not": []
                            }
                        }
                    }
                }
            }
        },
        "size": 0,
        "stored_fields": ["*"],
        "script_fields": {},
        "docvalue_fields": [
            {"field": "package.installed", "format": "date_time"},
            {"field": "vulnerability.detected_at", "format": "date_time"},
            {"field": "vulnerability.published_at", "format": "date_time"}
        ],
        "_source": {"excludes": []},
        "query": {
            "bool": {
                "must": [],
                "filter": [
                    {"match_all": {}},
                    {
                        "match_phrase": {
                            "wazuh.cluster.name": {"query": "wazuh"}
                        }
                    }
                ],
                "should": [],
                "must_not": []
            }
        }
    }

    try:
        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL2,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # ปิดการตรวจสอบ SSL หากใช้ self-signed certificates
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # แปลงผลลัพธ์จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", {})

        # สร้างผลลัพธ์ที่ตอบกลับ
        results = [{"severity": key, "count": value["doc_count"]} for key, value in buckets.items()]
        return jsonify(results), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error querying Elasticsearch: {e}"}), 500


@app.route("/api/latest_alert", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_latest_alert():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        query = {
            "size": 1,
            "sort": [
                {
                    "@timestamp": {
                        "order": "desc"
                    }
                }
            ]
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        return jsonify(hits)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching latest alert: {e}"}), 500


@app.route("/api/mitre_alert", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_mitre_alert():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        query = {
            "size": 1,
            "query": {
                "bool": {
                    "must": [
                        {
                            "exists": {
                                "field": "rule.mitre.id"
                            }
                        }
                    ]
                }
            },
            "sort": [
                {
                    "@timestamp": {
                        "order": "desc"
                    }
                }
            ]
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        return jsonify(hits)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching MITRE alert: {e}"}), 500

# Count log
@app.route("/api/mitre_techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_mitre_techniques():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        query = {
            "size": 0,
            "aggs": {
                "mitre_techniques": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "size": 20
                    }
                }
            }
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        aggregations = data.get("aggregations", {}).get("mitre_techniques", {}).get("buckets", [])

        # Return the aggregated data
        return jsonify(aggregations)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching MITRE techniques: {e}"}), 500




@app.route("/api/today-attacks", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_today_attacks():
    """
    ดึงข้อมูลการโจมตีของทุกประเทศที่เกิดขึ้นในวันนี้
    """
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "GeoLocation.country_name",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 100  # ขยายขนาดเพื่อรวมทุกประเทศ
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "script_fields": {},
            "docvalue_fields": [
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {"excludes": ["@timestamp"]},
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now/d",  # เริ่มต้นวันนี้
                                    "lte": "now",   # จนถึงตอนนี้
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        # ตรวจสอบสถานะ HTTP
        response.raise_for_status()

        # ดึงข้อมูล JSON จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # แปลงข้อมูลสำหรับการตอบกลับ
        results = [{"country": bucket["key"], "count": bucket["doc_count"]} for bucket in buckets]

        return jsonify(results)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching today attacks: {e}"}), 500





@app.route("/api/today_mitre_techniques", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_mitre_techniques_today():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")
        

        # Elasticsearch query with date range
        query = {
            "size": 0,
            "query": {
                "range": {
                    "@timestamp": {  # ปรับฟิลด์ให้ตรงกับที่ใช้ใน Elasticsearch
                        "gte": "now/d",  # เริ่มต้นวันนี้
                        "lte": "now", 
                        "format": "strict_date_optional_time"
                    }
                }
            },
            "aggs": {
                "mitre_techniques": {
                    "terms": {
                        "field": "rule.mitre.technique",
                        "size": 100
                    }
                }
            }
        }

        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False
        )

        response.raise_for_status()

        data = response.json()
        aggregations = data.get("aggregations", {}).get("mitre_techniques", {}).get("buckets", [])

        # Return the aggregated data
        return jsonify(aggregations)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching MITRE techniques: {e}"}), 500




@app.route("/api/top_rule_descriptions", methods=["GET"])
@jwt_required()  # Require JWT authentication
def get_top_rule_descriptions():
    try:
        current_user = get_jwt_identity()
        print(f"Request made by: {current_user}")

        # Elasticsearch Query
        query = {
            "aggs": {
                "2": {
                    "terms": {
                        "field": "rule.description",
                        "order": {
                            "_count": "desc"
                        },
                        "size": 100  # ดึง 5 อันดับแรก
                    }
                }
            },
            "size": 0,
            "stored_fields": ["*"],
            "docvalue_fields": [
                {"field": "timestamp", "format": "date_time"}
            ],
            "_source": {
                "excludes": ["@timestamp"]
            },
            "query": {
                "bool": {
                    "filter": [
                        {"match_all": {}},
                        {
                            "range": {
                                "timestamp": {
                                    "gte": "now/d",  # เริ่มต้นวันนี้
                                    "lte": "now", 
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            }
        }

        # ส่งคำขอไปยัง Elasticsearch
        response = requests.post(
            ES_URL,
            auth=(ES_USERNAME, ES_PASSWORD),
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            verify=False  # ปิด SSL Verification หากจำเป็น
        )

        response.raise_for_status()

        # แยกผลลัพธ์จาก Elasticsearch
        data = response.json()
        buckets = data.get("aggregations", {}).get("2", {}).get("buckets", [])

        # จัดข้อมูลสำหรับการส่งกลับ
        top_descriptions = [
            {"rule_description": bucket["key"], "count": bucket["doc_count"]}
            for bucket in buckets
        ]

        return jsonify(top_descriptions)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching top rule descriptions: {e}"}), 500




if __name__ == "__main__":
    app.run(debug=True)
