import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime
import json
import concurrent.futures
import numpy as np

# 지역 코드 매핑
REGION_CODES = {
    'A000': '서울',
    'H000': '부산', 
    'I000': '대구',
    'C000': '인천',
    'D000': '광주',
    'E000': '대전',
    'F000': '울산',
    'G000': '세종',
    'B000': '경기',
    'J000': '강원',
    'K000': '충북',
    'L000': '충남',
    'M000': '전북',
    'N000': '전남',
    'O000': '경북',
    'P000': '경남',
    'Q000': '제주'
}

class RegionalAnalyzer:
    def __init__(self):
        self.base_url = 'https://bff-general.albamon.com'
        self.headers = {
            'Accept': '*/*',
            'User-Agent': 'job-site-monitor/1.0.0',
            'origin': 'https://www.albamon.com',
            'Content-Type': 'application/json',
            'cookie': 'ConditionId=25C99562-77E3-40EB-A750-DA27D2D03C54; ab.storage.deviceId.7a5f1472-069a-4372-8631-2f711442ee40=%7B%22g%22%3A%22efb20921-d9c8-43dd-3c27-8a1487d7d2c4%22%2C%22c%22%3A1756907811760%2C%22l%22%3A1756943038663%7D; AM_USER_UUID=e69544f8-bed4-4fc3-94c7-6efac20359f7; ab.storage.sessionId.7a5f1472-069a-4372-8631-2f711442ee40=%7B%22g%22%3A%22898147fc-a8ba-6427-1f60-647c10d3514e%22%2C%22e%22%3A1756945521947%2C%22c%22%3A1756943038661%2C%22l%22%3A1756943721947%7D'
        }
        # 고급 캐시 시스템
        self._cache = {}
        self._cache_timeout = 300  # 5분 캐시
        self._request_session = requests.Session()  # 연결 재사용
        self._request_session.headers.update(self.headers)
        # 성능 카운터
        self.performance_stats = {
            'api_calls': 0,
            'cache_hits': 0,
            'total_processing_time': 0
        }
    
    def _get_cache_key(self, region_code, search_period_type, max_pages):
        """캐시 키 생성"""
        return f"{region_code}_{search_period_type}_{max_pages}_{datetime.now().strftime('%H_%M')[:4]}"  # 10분 단위로 캐시
    
    def _get_from_cache(self, cache_key):
        """캐시에서 데이터 조회"""
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_timeout:
                self.performance_stats['cache_hits'] += 1
                return cached_data
            else:
                # 만료된 캐시 삭제
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key, data):
        """캐시에 데이터 저장"""
        self._cache[cache_key] = (data, time.time())

    def categorize_job_posting(self, job):
        """
        공고 소스 및 유형 분류
        """
        # 소스 분류
        if job.get('jobkoreaRecruitNo', 0) != 0:
            source = 'JOBKOREA'
        elif job.get('externalRecruitSite') == 'WN':
            source = 'WORKNET'
        else:
            source = 'ALBAMON'
        
        # 유료/무료 분류 (ALBAMON 공고만)
        is_paid = False
        product_count = 0
        if source == 'ALBAMON':
            product_count = job.get('paidService', {}).get('totalProductCount', 0)
            is_paid = product_count > 0
        
        return {
            'source': source,
            'is_paid': is_paid,
            'product_count': product_count
        }

    def search_regional_jobs(self, region_code, page=1, size=200, search_period_type='ALL'):
        """
        지역별 공고 검색
        """
        request_body = {
            "pagination": {
                "page": int(page),
                "size": int(size)
            },
            "recruitListType": "AREA",
            "sortTabCondition": {
                "searchPeriodType": str(search_period_type),
                "sortType": "DEFAULT"
            },
            "condition": {
                "areas": [
                    {
                        "si": region_code,
                        "gu": "",
                        "dong": ""
                    }
                ],
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
                "educationType": "ALL",
                "selectedArea": {
                    "si": "",
                    "gu": "",
                    "dong": ""
                }
            }
        }
        
        try:
            # 세션 기반 요청으로 연결 재사용 (속도 향상)
            response = self._request_session.post(
                f'{self.base_url}/recruit/search',
                json=request_body,
                timeout=15  # 타임아웃 단축
            )
            response.raise_for_status()
            data = response.json()
            self.performance_stats['api_calls'] += 1
            
            # 올바른 JSON 경로로 공고 데이터 추출
            jobs = data.get('base', {}).get('normal', {}).get('collection', [])
            
            return {
                'result': {'recruitList': jobs},
                'base': data.get('base', {}),
                '_debug_info': {
                    'original_job_count': len(jobs),
                    'region_code': region_code,
                    'json_structure': 'base.normal.collection'
                }
            }
        except requests.exceptions.RequestException as e:
            st.error(f"지역별 API 요청 실패: {e}")
            return None

    def fetch_page_data(self, region_code, page, size, search_period_type):
        """단일 페이지 데이터 가져오기 (병렬 처리용)"""
        try:
            response = self.search_regional_jobs(region_code, page, size, search_period_type)
            if response:
                jobs = response.get('result', {}).get('recruitList', [])
                return {'page': page, 'jobs': jobs, 'success': True}
            return {'page': page, 'jobs': [], 'success': False}
        except Exception as e:
            st.error(f"페이지 {page} 요청 실패: {e}")
            return {'page': page, 'jobs': [], 'success': False}

    def analyze_regional_jobs(self, region_code, region_name, search_period_type='ALL', max_pages=3):
        """
        지역별 공고 분석 (유료/무료 포함) - 최적화된 버전
        """
        try:
            # 캐시 확인
            cache_key = self._get_cache_key(region_code, search_period_type, max_pages)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                st.success("⚡ 캐시된 데이터를 사용합니다 (5분 캐시)")
                return cached_result
            # 첫 번째 페이지로 전체 공고 수 확인
            first_response = self.search_regional_jobs(region_code, 1, 200, search_period_type)
            if not first_response:
                return None
                
            total_count = first_response.get('base', {}).get('pagination', {}).get('totalCount', 0)
            calculated_max_pages = (total_count + 199) // 200 if total_count > 0 else 1
            actual_max_pages = min(max_pages, calculated_max_pages)
            
            st.info(f"{region_name} 전체 공고 수: {total_count:,}개 ({calculated_max_pages} 페이지)")
            st.info(f"분석 대상: {actual_max_pages}페이지 (샘플링)")
            
            if total_count == 0:
                return {
                    'region_name': region_name,
                    'region_code': region_code,
                    'total_count': 0,
                    'albamon_count': 0,
                    'albamon_free_count': 0,
                    'albamon_paid_count': 0,
                    'jobkorea_count': 0,
                    'worknet_count': 0,
                    'sample_jobs': []
                }
            
            # 병렬로 여러 페이지 분석 (속도 대폭 개선)
            all_jobs = []
            start_time = time.time()
            
            # 더 많은 동시 연결 허용 (속도 대폭 향상)
            max_workers = min(actual_max_pages, 10)  # 5 → 10으로 증가
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 모든 페이지를 병렬로 요청
                future_to_page = {
                    executor.submit(self.fetch_page_data, region_code, page, 200, search_period_type): page 
                    for page in range(1, actual_max_pages + 1)
                }
                
                # 진행 상황 표시용
                completed_count = 0
                progress_placeholder = st.empty()
                
                for future in concurrent.futures.as_completed(future_to_page):
                    page = future_to_page[future]
                    result = future.result()
                    
                    completed_count += 1
                    progress_placeholder.info(f"📡 API 호출 진행 중... {completed_count}/{actual_max_pages} 페이지 완료")
                    
                    if result['success']:
                        all_jobs.extend(result['jobs'])
            
            elapsed_time = time.time() - start_time
            st.success(f"⚡ {actual_max_pages}페이지 병렬 처리 완료 ({elapsed_time:.1f}초)")
            progress_placeholder.empty()
            
            # 초고속 벡터화 분류 처리
            start_classification = time.time()
            
            if not all_jobs:
                counters = {'albamon_count': 0, 'albamon_free_count': 0, 'albamon_paid_count': 0, 'jobkorea_count': 0, 'worknet_count': 0}
                sample_jobs = []
            else:
                # NumPy 벡터화로 초고속 처리
                job_count = len(all_jobs)
                
                # 벡터화를 위한 데이터 추출
                jobkorea_nos = np.array([job.get('jobkoreaRecruitNo', 0) for job in all_jobs])
                external_sites = np.array([job.get('externalRecruitSite', '') for job in all_jobs])
                product_counts = np.array([job.get('paidService', {}).get('totalProductCount', 0) for job in all_jobs])
                
                # 벡터화된 분류
                is_jobkorea = jobkorea_nos != 0
                is_worknet = (external_sites == 'WN') & ~is_jobkorea  # JOBKOREA가 우선
                is_albamon = ~is_jobkorea & ~is_worknet
                is_paid = is_albamon & (product_counts > 0)
                is_free = is_albamon & (product_counts == 0)
                
                # 빠른 카운팅
                counters = {
                    'jobkorea_count': int(np.sum(is_jobkorea)),
                    'worknet_count': int(np.sum(is_worknet)),
                    'albamon_count': int(np.sum(is_albamon)),
                    'albamon_paid_count': int(np.sum(is_paid)),
                    'albamon_free_count': int(np.sum(is_free))
                }
                
                # 샘플 데이터 (처음 10개만, 기존 방식 유지)
                sample_jobs = []
                for i in range(min(10, job_count)):
                    job = all_jobs[i]
                    source = 'JOBKOREA' if is_jobkorea[i] else 'WORKNET' if is_worknet[i] else 'ALBAMON'
                    sample_jobs.append({
                        'recruitNo': job.get('recruitNo'),
                        'title': job.get('recruitTitle', '')[:40] + '...',
                        'source': source,
                        'is_paid': bool(is_paid[i]) if is_albamon[i] else False,
                        'product_count': int(product_counts[i]) if is_albamon[i] else 0,
                        'pay': job.get('pay', ''),
                        'workplaceArea': job.get('workplaceArea', ''),
                        'jobkoreaRecruitNo': int(jobkorea_nos[i]),
                        'externalRecruitSite': external_sites[i],
                        'paidService': str(job.get('paidService', {}))
                    })
            
            classification_time = time.time() - start_classification
            st.info(f"📊 {len(all_jobs):,}개 공고 분류 완료 ({classification_time:.2f}초)")
            
            # 카운터에서 값 추출
            albamon_count = counters['albamon_count']
            albamon_free_count = counters['albamon_free_count'] 
            albamon_paid_count = counters['albamon_paid_count']
            jobkorea_count = counters['jobkorea_count']
            worknet_count = counters['worknet_count']
            
            # 외부 연동 공고가 있을 때만 간단히 표시
            external_count = jobkorea_count + worknet_count
            if external_count > 0:
                st.success(f"🔗 외부 연동 공고 {external_count:,}개 발견 (잡코리아: {jobkorea_count:,}개, 워크넷: {worknet_count:,}개)")
            
            # 집계 오류 검증 (오류 시에만 표시)
            if albamon_free_count + albamon_paid_count != albamon_count:
                st.error(f"⚠️ 집계 오류 발견 - 수정 중...")
            
            # 비율에 따른 전체 추정 (디버깅 정보 최소화)
            if len(all_jobs) > 0 and len(all_jobs) < total_count:
                # 샘플 비율로 전체 추정
                ratio = total_count / len(all_jobs)
                
                albamon_estimated = int(albamon_count * ratio)
                albamon_free_estimated = int(albamon_free_count * ratio)
                albamon_paid_estimated = int(albamon_paid_count * ratio)
                jobkorea_estimated = int(jobkorea_count * ratio)
                worknet_estimated = int(worknet_count * ratio)
                
                # 추정 완료 알림만 표시
                st.info(f"📊 샘플 {len(all_jobs):,}개 분석 → 전체 {total_count:,}개 추정 완료")
                    
            else:
                # 전체 분석 완료
                albamon_estimated = albamon_count
                albamon_free_estimated = albamon_free_count
                albamon_paid_estimated = albamon_paid_count
                jobkorea_estimated = jobkorea_count
                worknet_estimated = worknet_count
            
            # 최종 검증 (오류 시에만 자동 수정)
            if albamon_free_estimated + albamon_paid_estimated != albamon_estimated:
                albamon_estimated = albamon_free_estimated + albamon_paid_estimated
            
            # 결과 생성
            result = {
                'region_name': region_name,
                'region_code': region_code,
                'total_count': total_count,
                'analyzed_count': len(all_jobs),
                'albamon_count': albamon_estimated,
                'albamon_free_count': albamon_free_estimated,
                'albamon_paid_count': albamon_paid_estimated,
                'jobkorea_count': jobkorea_estimated,
                'worknet_count': worknet_estimated,
                'sample_jobs': sample_jobs,
                'sample_stats': {
                    'albamon_sample': albamon_count,
                    'albamon_free_sample': albamon_free_count,
                    'albamon_paid_sample': albamon_paid_count,
                    'jobkorea_sample': jobkorea_count,
                    'worknet_sample': worknet_count
                },
                'performance': {
                    'api_time': elapsed_time,
                    'classification_time': classification_time,
                    'total_jobs_processed': len(all_jobs),
                    'api_calls_made': self.performance_stats['api_calls'],
                    'cache_hits': self.performance_stats['cache_hits'],
                    'avg_time_per_page': elapsed_time / max(actual_max_pages, 1),
                    'processing_speed': len(all_jobs) / max(classification_time, 0.001),
                    'concurrent_workers': max_workers
                }
            }
            
            # 결과를 캐시에 저장
            self._set_cache(cache_key, result)
            st.success(f"💾 분석 결과가 캐시에 저장되었습니다 (5분간 유효)")
            
            return result
            
        except Exception as e:
            st.error(f"지역별 분석 중 오류 발생: {e}")
            return None

def render_regional_dashboard(results):
    """지역별 대시보드 렌더링"""
    if not results or results['total_count'] == 0:
        st.info("해당 지역에 공고가 없습니다.")
        return
        
    st.header(f"🏙️ {results['region_name']} 공고 분석 결과")
    
    # 메트릭 카드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📊 전체 공고 수",
            value=f"{results['total_count']:,}개"
        )
    
    with col2:
        st.metric(
            label="🏢 알바몬 자사",
            value=f"{results['albamon_count']:,}개",
            delta=f"{(results['albamon_count']/results['total_count']*100):.1f}%"
        )
    
    with col3:
        st.metric(
            label="🆓 무료 공고",
            value=f"{results['albamon_free_count']:,}개",
            delta=f"{(results['albamon_free_count']/results['total_count']*100):.1f}%"
        )
    
    with col4:
        st.metric(
            label="🔗 외부 연동",
            value=f"{results['jobkorea_count'] + results['worknet_count']:,}개",
            delta=f"{((results['jobkorea_count'] + results['worknet_count'])/results['total_count']*100):.1f}%"
        )
    
    # 차트 섹션
    col1, col2 = st.columns(2)
    
    with col1:
        # 소스별 파이 차트
        fig_source = go.Figure(data=[go.Pie(
            labels=['알바몬 자사', '잡코리아', '워크넷'],
            values=[results['albamon_count'], results['jobkorea_count'], results['worknet_count']],
            hole=.3,
            marker_colors=['#FF6B6B', '#4ECDC4', '#45B7D1']
        )])
        fig_source.update_layout(title="소스별 분포")
        st.plotly_chart(fig_source, use_container_width=True)
    
    with col2:
        # 바 차트
        fig_bar = go.Figure(data=[
            go.Bar(
                x=['무료 공고', '유료 공고', '잡코리아', '워크넷'],
                y=[results['albamon_free_count'], results['albamon_paid_count'], 
                   results['jobkorea_count'], results['worknet_count']],
                marker_color=['#95E1D3', '#F38BA8', '#4ECDC4', '#45B7D1']
            )
        ])
        fig_bar.update_layout(title="공고 유형별 비교", yaxis_title="공고 수")
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # 상세 정보 테이블
    st.subheader("📋 상세 분석 결과")
    detail_data = {
        '구분': ['알바몬 자사', '  └ 무료 공고', '  └ 유료 공고', '잡코리아', '워크넷', '전체'],
        '공고 수': [
            f"{results['albamon_count']:,}",
            f"{results['albamon_free_count']:,}",
            f"{results['albamon_paid_count']:,}",
            f"{results['jobkorea_count']:,}",
            f"{results['worknet_count']:,}",
            f"{results['total_count']:,}"
        ],
        '비율 (%)': [
            f"{results['albamon_count']/results['total_count']*100:.2f}",
            f"{results['albamon_free_count']/results['total_count']*100:.2f}",
            f"{results['albamon_paid_count']/results['total_count']*100:.2f}",
            f"{results['jobkorea_count']/results['total_count']*100:.2f}",
            f"{results['worknet_count']/results['total_count']*100:.2f}",
            "100.00"
        ]
    }
    
    df_detail = pd.DataFrame(detail_data)
    st.dataframe(df_detail, use_container_width=True)
    
    # 샘플 공고 데이터
    if results['sample_jobs']:
        st.subheader("📋 샘플 공고 데이터")
        st.write(f"분석된 샘플: {results['analyzed_count']:,}개 공고 중 상위 10개")
        
        sample_df = pd.DataFrame(results['sample_jobs'])
        st.dataframe(sample_df, use_container_width=True)
    
    # JSON 다운로드
    st.download_button(
        label="📥 결과 JSON 다운로드",
        data=json.dumps(results, indent=2, ensure_ascii=False),
        file_name=f"{results['region_name']}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )

def main():
    st.set_page_config(
        page_title="지역별 공고 분석",
        page_icon="🏙️",
        layout="wide"
    )

    st.title("🏙️ 지역별 공고 분석 대시보드")
    st.markdown("지역별 무료/유료 공고 현황을 분석합니다.")

    analyzer = RegionalAnalyzer()

    # 사이드바
    with st.sidebar:
        st.header("🏙️ 지역 선택")
        
        selected_region_code = st.selectbox(
            "분석할 지역을 선택하세요",
            options=list(REGION_CODES.keys()),
            format_func=lambda x: f"{REGION_CODES[x]} ({x})"
        )
        
        period_type = st.selectbox(
            "기간 선택",
            options=['ALL', 'TODAY'],
            format_func=lambda x: "전체" if x == 'ALL' else "오늘"
        )
        
        max_pages = st.slider(
            "분석할 페이지 수 (샘플링)",
            min_value=1,
            max_value=10,
            value=3,
            help="더 많은 페이지를 분석할수록 정확도가 높아지지만 시간이 오래 걸립니다."
        )
        
        if st.button("🔍 지역별 분석 시작", type="primary"):
            st.session_state.run_regional_analysis = True
            st.session_state.selected_region = selected_region_code
            st.session_state.selected_period = period_type
            st.session_state.selected_max_pages = max_pages

    # 지역별 분석 실행
    if hasattr(st.session_state, 'run_regional_analysis') and st.session_state.run_regional_analysis:
        region_code = st.session_state.selected_region
        region_name = REGION_CODES[region_code]
        period_type = st.session_state.selected_period
        max_pages = st.session_state.selected_max_pages
        
        with st.spinner(f"{region_name} 지역 공고를 분석하고 있습니다..."):
            results = analyzer.analyze_regional_jobs(
                region_code, 
                region_name, 
                period_type, 
                max_pages
            )
        
        if results:
            render_regional_dashboard(results)
        
        st.session_state.run_regional_analysis = False

    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
    <small>지역별 공고 분석 대시보드 | 무료/유료 공고 구분 기능 포함</small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()