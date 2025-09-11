import requests
import json

def test_page_1340():
    """1340페이지 직접 테스트"""
    
    url = 'https://bff-general.albamon.com/recruit/search'
    headers = {
        'Accept': '*/*',
        'User-Agent': 'job-site-monitor/1.0.0',
        'origin': 'https://www.albamon.com',
        'Content-Type': 'application/json',
        'cookie': 'ConditionId=25C99562-77E3-40EB-A750-DA27D2D03C54; ab.storage.deviceId.7a5f1472-069a-4372-8631-2f711442ee40=%7B%22g%22%3A%22efb20921-d9c8-43dd-3c27-8a1487d7d2c4%22%2C%22c%22%3A1756907811760%2C%22l%22%3A1756943038663%7D; AM_USER_UUID=e69544f8-bed4-4fc3-94c7-6efac20359f7; ab.storage.sessionId.7a5f1472-069a-4372-8631-2f711442ee40=%7B%22g%22%3A%22898147fc-a8ba-6427-1f60-647c10d3514e%22%2C%22e%22%3A1756945521947%2C%22c%22%3A1756943038661%2C%22l%22%3A1756943721947%7D'
    }
    
    request_body = {
        "pagination": {
            "page": 1340,
            "size": 200
        },
        "recruitListType": "SEARCH",
        "sortTabCondition": {
            "searchPeriodType": "ALL",
            "sortType": "RELATION"
        },
        "condition": {
            "areas": [],
            "employmentTypes": [],
            "excludeKeywords": [],
            "excludeBar": False,
            "excludeNegoAge": False,
            "excludeNegoWorkWeek": False,
            "excludeNegoWorkTime": False,
            "excludeNegoGender": False,
            "parts": [],
            "similarDongJoin": False,
            "workDayTypes": [],
            "workPeriodTypes": [],
            "workTimeTypes": [],
            "workWeekTypes": [],
            "endWorkTime": "",
            "startWorkTime": "",
            "includeKeyword": "",
            "excludeKeywordList": [],
            "age": 0,
            "genderType": "NONE",
            "moreThanEducation": False,
            "educationType": "ALL"
        },
        "extensionCondition": {
            "search": {
                "keyword": "",
                "featureCode": "",
                "disableExceptedConditions": []
            }
        }
    }
    
    try:
        print(f"[INFO] 페이지 1340 요청 중...")
        response = requests.post(url, json=request_body, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        jobs = data.get('base', {}).get('normal', {}).get('collection', [])
        total_count = data.get('base', {}).get('pagination', {}).get('totalCount', 0)
        
        print(f"[SUCCESS] 페이지 1340에서 {len(jobs)}개 공고 발견")
        print(f"[INFO] 전체 공고 수: {total_count:,}개")
        
        # 소스별 분류
        albamon_count = 0
        jobkorea_count = 0
        worknet_count = 0
        
        worknet_jobs = []
        jobkorea_jobs = []
        
        for i, job in enumerate(jobs):
            # 분류 로직
            if job.get('jobkoreaRecruitNo', 0) != 0:
                source = 'JOBKOREA'
                jobkorea_count += 1
                if len(jobkorea_jobs) < 3:
                    jobkorea_jobs.append({
                        'index': i+1,
                        'recruitNo': job.get('recruitNo'),
                        'title': job.get('recruitTitle', '')[:50],
                        'jobkoreaRecruitNo': job.get('jobkoreaRecruitNo')
                    })
            elif job.get('externalRecruitSite') == 'WN':
                source = 'WORKNET'
                worknet_count += 1
                if len(worknet_jobs) < 3:
                    worknet_jobs.append({
                        'index': i+1,
                        'recruitNo': job.get('recruitNo'),
                        'title': job.get('recruitTitle', '')[:50],
                        'externalRecruitSite': job.get('externalRecruitSite'),
                        'externalRecruitOriginKey': job.get('externalRecruitOriginKey', '')[:20]
                    })
            else:
                source = 'ALBAMON'
                albamon_count += 1
        
        print(f"\n[RESULT] 페이지 1340 분석 결과:")
        print(f"  알바몬 자사: {albamon_count}개")
        print(f"  잡코리아: {jobkorea_count}개")
        print(f"  워크넷: {worknet_count}개")
        
        if worknet_jobs:
            print(f"\n[FOUND] 워크넷 공고 발견! (처음 3개):")
            for job in worknet_jobs:
                print(f"  #{job['index']}: {job['title']}")
                print(f"    - recruitNo: {job['recruitNo']}")
                print(f"    - externalRecruitSite: {job['externalRecruitSite']}")
                print(f"    - externalRecruitOriginKey: {job['externalRecruitOriginKey']}")
                print()
        
        if jobkorea_jobs:
            print(f"\n[FOUND] 잡코리아 공고 발견! (처음 3개):")
            for job in jobkorea_jobs:
                print(f"  #{job['index']}: {job['title']}")
                print(f"    - recruitNo: {job['recruitNo']}")
                print(f"    - jobkoreaRecruitNo: {job['jobkoreaRecruitNo']}")
                print()
        
        # JSON 파일로 저장
        with open('page_1340_response.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("[SAVE] 전체 응답을 'page_1340_response.json'에 저장했습니다.")
        
        return {
            'total_jobs': len(jobs),
            'albamon': albamon_count,
            'jobkorea': jobkorea_count,
            'worknet': worknet_count,
            'worknet_jobs': worknet_jobs,
            'jobkorea_jobs': jobkorea_jobs
        }
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API 요청 실패: {e}")
        return None

if __name__ == "__main__":
    result = test_page_1340()
    
    if result and (result['worknet'] > 0 or result['jobkorea'] > 0):
        print(f"\n[CONCLUSION] 페이지 1340에 실제로 외부 공고가 존재합니다!")
        print(f"   - 워크넷: {result['worknet']}개")
        print(f"   - 잡코리아: {result['jobkorea']}개")
        print(f"\n[ISSUE] Streamlit 앱에서 1340 주변 페이지를 검색하지 못한 것 같습니다.")
        print(f"   페이지 검색 범위를 늘려야 합니다!")
    else:
        print(f"\n[STRANGE] 이상합니다. 1340페이지에서 외부 공고를 찾지 못했습니다.")