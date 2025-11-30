"""ES 인덱스 구조 및 데이터 확인 스크립트"""
import os
import sys
import json

# 환경변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("dotenv를 사용할 수 없습니다. 환경변수를 직접 설정하세요.")

sys.path.insert(0, os.path.dirname(__file__))

from tools.es_search import get_es_client

print("=" * 60)
print("ES 인덱스 구조 및 데이터 확인")
print("=" * 60)

es_host = os.getenv("ES_HOST")
es_index = os.getenv("ES_INDEX", "restaurant_docs")

print(f"\n[환경변수]")
print(f"ES_HOST: {es_host}")
print(f"ES_INDEX: {es_index}")

if not es_host:
    print("\n[오류] ES_HOST가 설정되지 않았습니다.")
    sys.exit(1)

try:
    es = get_es_client()
    
    # 1. 인덱스 존재 확인
    print(f"\n[1] 인덱스 '{es_index}' 존재 확인...")
    exists = es.indices.exists(index=es_index)
    if exists:
        print(f"✅ 인덱스 '{es_index}' 존재함")
    else:
        print(f"❌ 인덱스 '{es_index}'가 존재하지 않습니다.")
        # 모든 인덱스 목록 확인
        all_indices = es.indices.get_alias(index="*")
        print(f"\n사용 가능한 인덱스 목록:")
        for idx in all_indices.keys():
            print(f"  - {idx}")
        sys.exit(1)
    
    # 2. 인덱스 매핑 확인
    print(f"\n[2] 인덱스 매핑 확인...")
    mapping = es.indices.get_mapping(index=es_index)
    props = mapping[es_index]["mappings"].get("properties", {})
    
    print(f"\n📋 필드 목록:")
    for field_name, field_info in list(props.items())[:20]:  # 처음 20개만
        field_type = field_info.get("type", "unknown")
        print(f"  - {field_name}: {field_type}")
        if "embedding" in field_name.lower() or field_type in ["dense_vector", "vector"]:
            print(f"    ⭐ 벡터 필드 발견! 차원: {field_info.get('dims', 'N/A')}")
    
    # 3. 문서 개수 확인
    print(f"\n[3] 문서 개수 확인...")
    count_result = es.count(index=es_index)
    total_docs = count_result.get("count", 0)
    print(f"총 문서 개수: {total_docs:,}개")
    
    if total_docs == 0:
        print("\n⚠️  인덱스에 데이터가 없습니다!")
        sys.exit(1)
    
    # 4. 샘플 문서 확인
    print(f"\n[4] 샘플 문서 (첫 1개) 확인...")
    sample_result = es.search(
        index=es_index,
        body={"size": 1}
    )
    
    if sample_result["hits"]["hits"]:
        sample_doc = sample_result["hits"]["hits"][0]
        doc_id = sample_doc["_id"]
        source = sample_doc["_source"]
        
        print(f"\n📄 문서 ID: {doc_id}")
        print(f"\n📋 실제 필드명들:")
        for key in list(source.keys())[:20]:  # 처음 20개만
            value = source[key]
            if isinstance(value, (list, dict)):
                value_str = f"{type(value).__name__} (길이: {len(value)})"
            else:
                value_str = str(value)[:50]  # 처음 50자만
            print(f"  - {key}: {value_str}")
        
        # 중요한 필드 확인
        print(f"\n🔍 주요 필드 값:")
        important_fields = [
            "Restaurant Name", "restaurant_name", "name", "Name",
            "Cuisines", "cuisines", "cuisine",
            "City", "city",
            "Address", "address",
        ]
        
        for field in important_fields:
            for key, value in source.items():
                if field.lower() in key.lower():
                    print(f"  - {key}: {value}")
                    break
        
        # embedding 필드 확인
        print(f"\n🔍 Embedding 필드:")
        for key in source.keys():
            if "embedding" in key.lower() or "vector" in key.lower():
                value = source[key]
                if isinstance(value, list):
                    print(f"  - {key}: 리스트 (길이: {len(value)})")
                else:
                    print(f"  - {key}: {type(value).__name__}")
        
    else:
        print("❌ 샘플 문서를 가져올 수 없습니다.")
    
    # 5. 간단한 검색 테스트
    print(f"\n[5] 검색 테스트...")
    test_queries = [
        "Korean",
        "Delhi",
        "restaurant",
        "*"  # 모든 문서
    ]
    
    for test_query in test_queries:
        try:
            if test_query == "*":
                body = {"query": {"match_all": {}}, "size": 5}
            else:
                body = {
                    "query": {
                        "multi_match": {
                            "query": test_query,
                            "fields": ["*"],  # 모든 필드
                            "type": "best_fields"
                        }
                    },
                    "size": 5
                }
            
            result = es.search(index=es_index, body=body)
            hits_count = len(result["hits"]["hits"])
            total_hits = result["hits"]["total"].get("value", 0)
            
            print(f"  쿼리 '{test_query}': {hits_count}개 결과 (전체 {total_hits}개)")
            
            if hits_count > 0:
                first_hit = result["hits"]["hits"][0]["_source"]
                # 어떤 필드에서 매칭되었는지 확인하기 위해 첫 번째 결과의 필드명 출력
                print(f"    → 첫 번째 결과 필드: {list(first_hit.keys())[:5]}")
        except Exception as e:
            print(f"  쿼리 '{test_query}' 실패: {e}")
    
    print("\n" + "=" * 60)
    print("확인 완료")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

