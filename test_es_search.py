"""ES 검색 직접 테스트 스크립트"""
import os
import sys

# 환경변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("dotenv를 사용할 수 없습니다. 환경변수를 직접 설정하세요.")

# tools 모듈 import
sys.path.insert(0, os.path.dirname(__file__))

from tools.es_search import search_es, dense_search
from tools.llm_tools import es_search_tool

print("=" * 60)
print("ES 검색 직접 테스트")
print("=" * 60)

# 환경변수 확인
es_host = os.getenv("ES_HOST")
es_index = os.getenv("ES_INDEX")
print(f"\n[환경변수 확인]")
print(f"ES_HOST: {es_host}")
print(f"ES_INDEX: {es_index}")
print(f"OPENROUTER_API_KEY: {'설정됨' if os.getenv('OPENROUTER_API_KEY') else '설정 안됨'}")

if not es_host or not es_index:
    print("\n[오류] ES_HOST 또는 ES_INDEX가 설정되지 않았습니다.")
    sys.exit(1)

# 테스트 쿼리
test_query = "한식"
print(f"\n[테스트 쿼리] {test_query}")

try:
    print("\n[1] Sparse 검색 테스트...")
    sparse_results = search_es(test_query, size=5)
    print(f"Sparse 검색 결과: {len(sparse_results)}개")
    if sparse_results:
        print(f"첫 번째 결과:")
        print(f"  ID: {sparse_results[0]['id']}")
        print(f"  Score: {sparse_results[0]['score']}")
        print(f"  Source keys: {list(sparse_results[0]['source'].keys())[:5]}")
    else:
        print("  [경고] 검색 결과가 없습니다!")
        
except Exception as e:
    print(f"  [오류] Sparse 검색 실패: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n[2] Dense 검색 테스트...")
    dense_results = dense_search(test_query, size=5)
    print(f"Dense 검색 결과: {len(dense_results)}개")
    if dense_results:
        print(f"첫 번째 결과:")
        print(f"  ID: {dense_results[0]['id']}")
        print(f"  Score: {dense_results[0]['score']}")
        print(f"  Source keys: {list(dense_results[0]['source'].keys())[:5]}")
    else:
        print("  [경고] 검색 결과가 없습니다!")
        
except Exception as e:
    print(f"  [오류] Dense 검색 실패: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n[3] es_search_tool 전체 테스트...")
    result = es_search_tool.invoke({"query": test_query, "size": 3})
    print(f"es_search_tool 결과:")
    print(result[:500] + "..." if len(result) > 500 else result)
    
except Exception as e:
    print(f"  [오류] es_search_tool 실패: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("테스트 완료")
print("=" * 60)

