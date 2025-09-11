import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import json
from regional_analyzer import (RegionalAnalyzer,
                               REGION_CODES,
                               render_regional_dashboard)


class AlbamonAnalyzer:
    def __init__(self):
        self.base_url = 'https://bff-general.albamon.com'
        self.headers = {
            'Accept': '*/*',
            'User-Agent': 'job-site-monitor/1.0.0',
            'origin': 'https://www.albamon.com',
            'Content-Type': 'application/json',
            'cookie': (
                'ConditionId=25C99562-77E3-40EB-A750-DA27D2D03C54; '
                'ab.storage.deviceId.7a5f1472-069a-4372-8631-2f711442ee40'
                '=%7B%22g%22%3A%22efb20921-d9c8-43dd-3c27-8a1487d7d2c4%22'
                '%2C%22c%22%3A1756907811760%2C%22l%22%3A1756943038663%7D; '
                'AM_USER_UUID=e69544f8-bed4-4fc3-94c7-6efac20359f7; '
                'ab.storage.sessionId.7a5f1472-069a-4372-8631-2f711442ee40'
                '=%7B%22g%22%3A%22898147fc-a8ba-6427-1f60-647c10d3514e%22'
                '%2C%22e%22%3A1756945521947%2C%22c%22%3A1756943038661%2C'
                '%22l%22%3A1756943721947%7D'
            )
        }

    def search_jobs(self, page=1, size=200, search_period_type='ALL',
                    sort_type='RELATION'):
        request_body = {
            "pagination": {
                "page": int(page),
                "size": int(size)
            },
            "recruitListType": "SEARCH",
            "sortTabCondition": {
                "searchPeriodType": str(search_period_type),
                "sortType": str(sort_type)
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
            response = requests.post(
                f'{self.base_url}/recruit/search',
                json=request_body,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # 올바른 JSON 경로로 공고 데이터 추출
            jobs = data.get('base', {}).get('normal', {}).get('collection', [])

            # 기존 형식에 맞추어 반환 (호환성 유지)
            return {
                'result': {'recruitList': jobs},
                'base': data.get('base', {}),
                '_debug_info': {
                    'original_job_count': len(jobs),
                    'json_structure': 'base.normal.collection'
                }
            }
        except requests.exceptions.RequestException as e:
            st.error(f"API 요청 실패: {e}")
            return None

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
        if source == 'ALBAMON':
            total_product_count = job.get(
                'paidService', {}).get('totalProductCount', 0)
            is_paid = total_product_count > 0

        return {
            'source': source,
            'is_paid': is_paid,
            'product_count': (
                job.get('paidService', {}).get('totalProductCount', 0)
                if source == 'ALBAMON' else None
            )
        }


    def find_source_range_efficient(self, search_period_type='ALL'):
        """
        🚀 경계 기반 효율적 탐색 - 자사>잡코리아>워크넷 순서를 활용한 간단한 경계 탐지
        """
        search_start_time = time.time()
        total_requests = 0
        
        # 전체 공고 수 확인
        first_response = self.search_jobs(1, 200, search_period_type)
        total_requests += 1
        
        if not first_response:
            return None, None, None, None, 0, {}, {}, 0

        total_count = (
            first_response.get('base', {})
            .get('pagination', {})
            .get('totalCount', 0)
        )
        max_pages = (total_count + 199) // 200 if total_count > 0 else 1

        st.info(f"🚀 경계 기반 탐색: 전체 {total_count:,}개 공고 ({max_pages}페이지)")

        # 1단계: 워크넷 경계 찾기 (끝페이지부터)
        st.info("🔍 워크넷 경계 탐색 중...")
        worknet_start = None
        worknet_end = None
        worknet_end_count = 0
        worknet_start_count = 0
        
        # 끝페이지에서 워크넷 확인
        try:
            response = self.search_jobs(max_pages, 200, search_period_type)
            total_requests += 1
            if response:
                jobs = response.get('result', {}).get('recruitList', [])
                worknet_count = sum(1 for job in jobs if job.get('externalRecruitSite') == 'WN')
                if worknet_count > 0:
                    worknet_end = max_pages
                    worknet_end_count = worknet_count
                    st.info(f"📍 워크넷 끝: {max_pages}페이지 ({worknet_count}개)")
        except Exception as e:
            st.warning(f"끝페이지 확인 오류: {e}")

        # 워크넷이 있으면 시작점 찾기
        if worknet_end:
            for i, page in enumerate(range(max_pages, 0, -1)):
                try:
                    # 진행 상황 표시
                    progress = (i + 1) / max_pages * 100
                    remaining_pages = max_pages - i
                    if i % 20 == 0 or page % 100 == 0:  # 20번마다 또는 100페이지마다 표시
                        st.info(f"🔍 워크넷 탐색: 페이지 {page} 확인 중 | 진행률: {progress:.1f}% | 남은 페이지: {remaining_pages}")
                    
                    response = self.search_jobs(page, 200, search_period_type)
                    total_requests += 1
                    
                    if not response:
                        continue

                    jobs = response.get('result', {}).get('recruitList', [])
                    if not jobs:
                        continue
                    
                    worknet_count = sum(1 for job in jobs if job.get('externalRecruitSite') == 'WN')
                    
                    if worknet_count > 0:
                        worknet_start = page
                        worknet_start_count = worknet_count
                    else:
                        # 워크넷이 없는 첫 페이지 발견 = 워크넷 시작점 확정
                        st.info(f"✅ 워크넷 시작점 확정: {worknet_start}~{worknet_end}페이지")
                        break
                        
                    time.sleep(0.002)
                    
                except Exception as e:
                    st.warning(f"페이지 {page} 검색 오류: {e}")
                    continue

        if worknet_start and worknet_end:
            st.success(f"✅ 워크넷: {worknet_start}~{worknet_end}페이지")
        else:
            st.info("📊 워크넷 공고 없음")

        # 2단계: 잡코리아 경계 찾기 (워크넷 앞쪽부터)
        st.info("🔍 잡코리아 경계 탐색 중...")
        jobkorea_start = None
        jobkorea_end = None
        jobkorea_end_count = 0
        jobkorea_start_count = 0
        search_start_page = worknet_start - 1 if worknet_start else max_pages
        
        # 워크넷 바로 앞 페이지에서 잡코리아 확인
        if search_start_page > 0:
            try:
                response = self.search_jobs(search_start_page, 200, search_period_type)
                total_requests += 1
                if response:
                    jobs = response.get('result', {}).get('recruitList', [])
                    jobkorea_count = sum(1 for job in jobs if job.get('jobkoreaRecruitNo', 0) != 0)
                    if jobkorea_count > 0:
                        jobkorea_end = search_start_page
                        jobkorea_end_count = jobkorea_count
                        st.info(f"📍 잡코리아 끝: {search_start_page}페이지 ({jobkorea_count}개)")
            except Exception as e:
                st.warning(f"잡코리아 끝페이지 확인 오류: {e}")

        # 잡코리아가 있으면 시작점 찾기
        if jobkorea_end:
            total_search_pages = search_start_page
            for i, page in enumerate(range(search_start_page, 0, -1)):
                try:
                    # 진행 상황 표시
                    progress = (i + 1) / total_search_pages * 100
                    remaining_pages = total_search_pages - i
                    if i % 20 == 0 or page % 100 == 0:  # 20번마다 또는 100페이지마다 표시
                        st.info(f"🔍 잡코리아 탐색: 페이지 {page} 확인 중 | 진행률: {progress:.1f}% | 남은 페이지: {remaining_pages}")
                    
                    response = self.search_jobs(page, 200, search_period_type)
                    total_requests += 1
                    
                    if not response:
                        continue

                    jobs = response.get('result', {}).get('recruitList', [])
                    if not jobs:
                        continue
                    
                    jobkorea_count = sum(1 for job in jobs if job.get('jobkoreaRecruitNo', 0) != 0)
                    
                    if jobkorea_count > 0:
                        jobkorea_start = page
                        jobkorea_start_count = jobkorea_count
                    else:
                        # 잡코리아가 없는 첫 페이지 발견 = 잡코리아 시작점 확정
                        st.info(f"✅ 잡코리아 시작점 확정: {jobkorea_start}~{jobkorea_end}페이지")
                        break
                        
                    time.sleep(0.002)
                    
                except Exception as e:
                    st.warning(f"페이지 {page} 검색 오류: {e}")
                    continue

        if jobkorea_start and jobkorea_end:
            st.success(f"✅ 잡코리아: {jobkorea_start}~{jobkorea_end}페이지")
        else:
            st.info("📊 잡코리아 공고 없음")

        # 3단계: 실제 확인한 개수 기반 계산 (추가 요청 없이)
        st.info("🔍 공고 수 계산 중...")
        jobkorea_counts = {}
        worknet_counts = {}
        
        # 잡코리아 공고 수 계산 (실제 확인한 개수 사용)
        if jobkorea_start and jobkorea_end:
            total_pages = jobkorea_end - jobkorea_start + 1
            if total_pages == 1:
                # 1페이지만 있으면 시작=끝이므로 시작 페이지 개수 사용
                jobkorea_counts[jobkorea_start] = jobkorea_start_count if jobkorea_start_count > 0 else jobkorea_end_count
            else:
                # 여러 페이지면 시작/끝은 실제 개수, 중간은 200개
                for page in range(jobkorea_start, jobkorea_end + 1):
                    if page == jobkorea_start:
                        jobkorea_counts[page] = jobkorea_start_count  # 실제 확인한 시작 페이지 개수
                    elif page == jobkorea_end:
                        jobkorea_counts[page] = jobkorea_end_count  # 실제 확인한 끝 페이지 개수
                    else:
                        jobkorea_counts[page] = 200  # 중간 페이지는 200개 (해당 소스만 있음)
        
        # 워크넷 공고 수 계산 (실제 확인한 개수 사용)
        if worknet_start and worknet_end:
            total_pages = worknet_end - worknet_start + 1
            if total_pages == 1:
                # 1페이지만 있으면 시작=끝이므로 시작 페이지 개수 사용
                worknet_counts[worknet_start] = worknet_start_count if worknet_start_count > 0 else worknet_end_count
            else:
                # 여러 페이지면 시작/끝은 실제 개수, 중간은 200개
                for page in range(worknet_start, worknet_end + 1):
                    if page == worknet_start:
                        worknet_counts[page] = worknet_start_count  # 실제 확인한 시작 페이지 개수
                    elif page == worknet_end:
                        worknet_counts[page] = worknet_end_count  # 실제 확인한 끝 페이지 개수
                    else:
                        worknet_counts[page] = 200  # 중간 페이지는 200개 (해당 소스만 있음)

        # 검색 소요시간 계산
        search_end_time = time.time()
        search_duration = search_end_time - search_start_time
        
        # 실제 공고 수 합계 계산
        total_jobkorea_count = sum(jobkorea_counts.values())
        total_worknet_count = sum(worknet_counts.values())

        # 결과 로깅
        if jobkorea_start and jobkorea_end:
            st.success(f"📊 잡코리아: {jobkorea_start}~{jobkorea_end}페이지 (총 {total_jobkorea_count:,}개)")
        if worknet_start and worknet_end:
            st.success(f"📊 워크넷: {worknet_start}~{worknet_end}페이지 (총 {total_worknet_count:,}개)")
            
        st.success(f"⚡ 경계 탐색 완료: {search_duration:.2f}초, 총 {total_requests}번 요청")

        return jobkorea_start, jobkorea_end, worknet_start, worknet_end, total_count, jobkorea_counts, worknet_counts, search_duration

    def analyze_page_sources(self, start_page=1, end_page=10,
                             search_period_type='ALL'):
        """
        특정 페이지 범위의 공고 소스 분석
        """
        page_results = []

        for page in range(start_page, end_page + 1):
            try:
                response = self.search_jobs(page, 200, search_period_type)
                if not response:
                    continue

                jobs = response.get('result', {}).get('recruitList', [])

                page_stats = {
                    'page': page,
                    'total_jobs': len(jobs),
                    'albamon': 0,
                    'jobkorea': 0,
                    'worknet': 0,
                    'sample_jobs': []
                }

                for job in jobs:
                    category = self.categorize_job_posting(job)
                    source = category['source']

                    if source == 'ALBAMON':
                        page_stats['albamon'] += 1
                    elif source == 'JOBKOREA':
                        page_stats['jobkorea'] += 1
                    elif source == 'WORKNET':
                        page_stats['worknet'] += 1

                # 각 페이지에서 처음 3개 공고만 샘플로 저장
                for job in jobs[:3]:
                    category = self.categorize_job_posting(job)
                    sample_info = {
                        'recruitNo': job.get('recruitNo'),
                        'title': job.get('recruitTitle', '')[:40] + '...',
                        'source': category['source'],
                        'is_paid': category['is_paid'],
                        'product_count': category['product_count'],
                        'jobkoreaRecruitNo': job.get('jobkoreaRecruitNo', 0),
                        'externalRecruitSite': job.get(
                            'externalRecruitSite', ''),
                    }
                    page_stats['sample_jobs'].append(sample_info)

                page_results.append(page_stats)
                time.sleep(0.1)

            except Exception as e:
                st.error(f"페이지 {page} 분석 중 오류: {e}")
                continue

        return page_results

    def comprehensive_job_analysis(self, search_period_type='ALL'):
        """
        효율적인 범위 탐색으로 공고 분석 - 범위를 찾으면 해당 범위만 정확히 카운팅
        """
        try:
            # 효율적인 범위 탐색 사용
            with st.spinner("🔍 효율적 범위 탐색으로 잡코리아/워크넷 범위 검색 중..."):
                result = self.find_source_range_efficient(search_period_type)
                    
            jobkorea_start, jobkorea_end, worknet_start, worknet_end, total_count, jobkorea_counts, worknet_counts, search_duration = result

            if total_count == 0:
                return {
                    'total_count': 0,
                    'albamon_count': 0,
                    'jobkorea_count': 0,
                    'worknet_count': 0,
                    'jobkorea_start_page': None,
                    'jobkorea_end_page': None,
                    'worknet_start_page': None,
                    'worknet_end_page': None,
                    'page_analysis': []
                }

            # 처음 5페이지 상세 분석 (샘플링용)
            page_results = self.analyze_page_sources(1, 5, search_period_type)

            # 🎯 정확한 공고 수 계산 (실제 페이지별 카운트 기반)
            # 잡코리아 실제 공고 수
            jobkorea_count = sum(jobkorea_counts.values()) if jobkorea_counts else 0
            
            # 워크넷 실제 공고 수  
            worknet_count = sum(worknet_counts.values()) if worknet_counts else 0
            
            # 자사 공고 수 = 전체 - 잡코리아 - 워크넷
            albamon_count = total_count - jobkorea_count - worknet_count

            return {
                'total_count': total_count,
                'albamon_count': max(0, albamon_count),
                'jobkorea_count': max(0, jobkorea_count),
                'worknet_count': max(0, worknet_count),
                'jobkorea_start_page': jobkorea_start,
                'jobkorea_end_page': jobkorea_end,
                'worknet_start_page': worknet_start,
                'worknet_end_page': worknet_end,
                'page_analysis': page_results,
                'detailed_counts': {
                    'jobkorea_by_page': jobkorea_counts,
                    'worknet_by_page': worknet_counts
                },
                'search_duration': search_duration,
                'optimization_info': {
                    'jobkorea_range': f"{jobkorea_start}~{jobkorea_end}" if jobkorea_start and jobkorea_end else "없음",
                    'worknet_range': f"{worknet_start}~{worknet_end}" if worknet_start and worknet_end else "없음",
                    'accuracy': "페이지별 실제 공고 수 기반 정확 계산",
                    'search_time': f"{search_duration:.2f}초"
                }
            }

        except Exception as e:
            st.error(f"분석 중 오류 발생: {e}")
            return None


def render_dashboard(results, title="공고 분석 결과"):
    """대시보드 렌더링 함수"""
    if not results or results['total_count'] == 0:
        st.info("분석할 공고가 없습니다.")
        return

    st.header(f"🔍 {title}")

    # 메트릭 카드
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="📊 전체 공고 수",
            value=f"{results['total_count']:,}개",
        )

    with col2:
        percentage = (
            results['albamon_count'] / results['total_count'] * 100
        )
        st.metric(
            label="🏢 자사 공고",
            value=f"{results['albamon_count']:,}개",
            delta=f"{percentage:.1f}%"
        )

    with col3:
        percentage = (
            results['jobkorea_count'] / results['total_count'] * 100
        )
        st.metric(
            label="💼 잡코리아 공고",
            value=f"{results['jobkorea_count']:,}개",
            delta=f"{percentage:.1f}%"
        )

    with col4:
        percentage = (
            results['worknet_count'] / results['total_count'] * 100
        )
        st.metric(
            label="🏛️ 워크넷 공고",
            value=f"{results['worknet_count']:,}개",
            delta=f"{percentage:.1f}%"
        )

    with col5:
        if results.get('search_duration'):
            st.metric(
                label="⏱️ 검색 시간",
                value=f"{results['search_duration']:.2f}초",
            )

    # 페이지 범위 정보 강조 표시
    if (results.get('jobkorea_start_page') or results.get('worknet_start_page')):
        st.subheader("🎯 공고 소스별 페이지 범위")
        col1, col2 = st.columns(2)

        with col1:
            if results.get('jobkorea_start_page'):
                start = results['jobkorea_start_page']
                end = results.get('jobkorea_end_page')
                if end:
                    range_text = f"{start}~{end}페이지"
                else:
                    range_text = f"{start}페이지부터"
                msg = f"💼 **잡코리아 공고 범위: {range_text}**"
                st.success(msg)
            else:
                st.info("💼 잡코리아 공고 없음")

        with col2:
            if results.get('worknet_start_page'):
                start = results['worknet_start_page']
                end = results.get('worknet_end_page')
                if end:
                    range_text = f"{start}~{end}페이지"
                else:
                    range_text = f"{start}페이지부터"
                msg = f"🏛️ **워크넷 공고 범위: {range_text}**"
                st.success(msg)
            else:
                st.info("🏛️ 워크넷 공고 없음")

    # 차트 섹션
    col1, col2 = st.columns(2)

    with col1:
        # 파이 차트
        fig_pie = go.Figure(data=[go.Pie(
            labels=['자사 공고', '잡코리아', '워크넷'],
            values=[results['albamon_count'],
                    results['jobkorea_count'],
                    results['worknet_count']],
            hole=.3,
            marker_colors=['#FF6B6B', '#4ECDC4', '#45B7D1']
        )])
        fig_pie.update_layout(title="공고 소스별 분포")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # 바 차트
        fig_bar = go.Figure(data=[
            go.Bar(
                x=['자사 공고', '잡코리아', '워크넷'],
                y=[results['albamon_count'],
                   results['jobkorea_count'],
                   results['worknet_count']],
                marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1']
            )
        ])
        fig_bar.update_layout(title="공고 수 비교", yaxis_title="공고 수")
        st.plotly_chart(fig_bar, use_container_width=True)

    # 상세 정보 테이블
    st.subheader("📋 상세 분석 결과")
    
    # 페이지 범위 정보 생성
    jobkorea_range = "N/A"
    if results.get('jobkorea_start_page'):
        start = results['jobkorea_start_page']
        end = results.get('jobkorea_end_page')
        if end:
            jobkorea_range = f"{start}~{end}"
        else:
            jobkorea_range = f"{start}+"
            
    worknet_range = "N/A"
    if results.get('worknet_start_page'):
        start = results['worknet_start_page']
        end = results.get('worknet_end_page')
        if end:
            worknet_range = f"{start}~{end}"
        else:
            worknet_range = f"{start}+"
    
    detail_data = {
        '구분': ['자사 공고', '잡코리아', '워크넷', '전체'],
        '공고 수': [
            f"{results['albamon_count']:,}",
            f"{results['jobkorea_count']:,}",
            f"{results['worknet_count']:,}",
            f"{results['total_count']:,}"
        ],
        '비율 (%)': [
            f"{results['albamon_count']/results['total_count']*100:.2f}",
            f"{results['jobkorea_count']/results['total_count']*100:.2f}",
            f"{results['worknet_count']/results['total_count']*100:.2f}",
            "100.00"
        ],
        '페이지 범위': [
            "1~자사끝",
            jobkorea_range,
            worknet_range,
            f"1~{((results['total_count'] + 199) // 200)}"
        ]
    }

    df_detail = pd.DataFrame(detail_data)
    st.dataframe(df_detail, use_container_width=True)

    # 최적화 정보 표시
    if results.get('optimization_info'):
        st.subheader("🎯 검색 최적화 결과")
        opt_info = results['optimization_info']
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**잡코리아 범위**: {opt_info.get('jobkorea_range', '없음')}")
        with col2:
            st.info(f"**워크넷 범위**: {opt_info.get('worknet_range', '없음')}")
            
        # 정확도 및 소요시간 정보
        col1, col2 = st.columns(2)
        with col1:
            if opt_info.get('accuracy'):
                st.success(f"✅ **정확도**: {opt_info['accuracy']}")
        with col2:
            if opt_info.get('search_time'):
                st.success(f"⏱️ **검색 시간**: {opt_info['search_time']}")
            
        # 상세 페이지별 공고 수 표시
        if results.get('detailed_counts'):
            with st.expander("📊 페이지별 상세 공고 수"):
                detail_counts = results['detailed_counts']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if detail_counts.get('jobkorea_by_page'):
                        st.write("**잡코리아 페이지별 공고 수:**")
                        for page, count in sorted(detail_counts['jobkorea_by_page'].items()):
                            st.write(f"  - 페이지 {page}: {count:,}개")
                    else:
                        st.write("**잡코리아**: 공고 없음")
                        
                with col2:
                    if detail_counts.get('worknet_by_page'):
                        st.write("**워크넷 페이지별 공고 수:**")
                        for page, count in sorted(detail_counts['worknet_by_page'].items()):
                            st.write(f"  - 페이지 {page}: {count:,}개")
                    else:
                        st.write("**워크넷**: 공고 없음")

    # JSON 다운로드 버튼
    st.download_button(
        label="📥 결과 JSON 다운로드",
        data=json.dumps(results, indent=2, ensure_ascii=False),
        file_name=(
            f"albamon_analysis_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        ),
        mime="application/json"
    )


def main():
    st.set_page_config(
        page_title="채용공고 모니터링",
        page_icon="📊",
        layout="wide"
    )

    # 토큰 인증 시스템
    SITE_TOKEN = "dkfqkcjsrnr1!"
    
    # 세션 상태 초기화
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # 인증되지 않은 경우 토큰 입력 화면 표시
    if not st.session_state.authenticated:
        # 간단한 다크 스타일
        st.markdown("""
        <style>
        .stApp {
            background-color: #1e1e1e;
        }
        .main .block-container {
            background-color: #2d2d2d;
            padding: 2rem;
            border-radius: 10px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.title("🔐 사이트 접근 인증")
        st.subheader("토큰을 입력하여 사이트에 접속하세요")
        
        # 토큰 입력
        token_input = st.text_input(
            "보안 토큰", 
            type="password", 
            key="token_input",
            placeholder="토큰을 입력하세요"
        )
        
        # 확인 버튼
        if st.button("접속하기", type="primary"):
            if token_input == SITE_TOKEN:
                st.session_state.authenticated = True
                st.success("인증 성공!")
                st.rerun()
            elif token_input:
                st.error("잘못된 토큰입니다.")
        
        # Enter 키로도 동작하도록
        if token_input == SITE_TOKEN:
            st.session_state.authenticated = True
            st.rerun()
            
        st.info("토큰을 입력하고 접속하기 버튼을 클릭하거나 Enter를 누르세요.")
        return
    
    # 인증된 사용자만 실제 컨텐츠 표시
    # 로그아웃 버튼
    if st.button("🚪 로그아웃", key="logout_btn"):
        st.session_state.authenticated = False
        st.rerun()

    # 전체 화면 레이아웃을 위한 CSS 스타일 추가
    st.markdown("""
    <style>
    .stColumn {
        width: 100% !important;
        flex: 1 1 0% !important;
        min-width: 0 !important;
    }
    .st-emotion-cache-1i94pul {
        width: 100% !important;
        flex: 1 1 0% !important;
    }
    .e1msl4mp1 {
        width: 100% !important;
    }
    .main .block-container {
        max-width: none !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    div[data-testid="column"] {
        width: fit-content !important;
        flex: unset !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("📊 채용공고 분석 대시보드")
    st.markdown(
        "워크넷과 잡코리아 연동 공고 현황을 실시간으로 모니터링합니다."
    )

    analyzer = AlbamonAnalyzer()
    regional_analyzer = RegionalAnalyzer()

    # 사이드바
    with st.sidebar:
        st.header("🔧 분석 옵션")

        if st.button("🔍 전체 공고 분석", type="primary"):
            st.session_state.run_analysis = True

        if st.button("📅 오늘 공고 분석"):
            st.session_state.check_today = True

        # 지역별 분석 설정
        st.markdown("#### 🏙️ 지역별 분석 설정")
        selected_region_code = st.selectbox(
            "지역 선택",
            options=list(REGION_CODES.keys()),
            format_func=lambda x: f"{REGION_CODES[x]}",
            key="sidebar_region_select"
        )

        regional_period = st.selectbox(
            "기간 선택",
            options=['ALL', 'TODAY'],
            format_func=lambda x: "전체" if x == 'ALL' else "오늘",
            key="sidebar_period_select"
        )

        if st.button("🏙️ 지역별 공고 분석"):
            st.session_state.run_regional_analysis = True
            st.session_state.selected_region_code = selected_region_code
            st.session_state.selected_regional_period = regional_period

        st.markdown("---")
        st.markdown("### 📝 정보")
        st.info("""
        **정렬 순서**
        1. 자사 공고
        2. 잡코리아 공고
        3. 워크넷 공고 (고용24)

        **🚀 효율적 범위 탐색 방법**
        
        **3단계 최적화 프로세스**
        - 🔍 1단계: 뒤에서부터 워크넷 범위 탐색 및 발견 시 중단
        - 🔍 2단계: 워크넷 앞쪽에서 잡코리아 범위 탐색 및 발견 시 중단  
        - 🔍 3단계: 확정된 범위에서만 정확한 공고 수 계산
        
        **조건**
        - 🎯 **잡코리아**: jobkoreaRecruitNo != 0
        - 🎯 **워크넷**: externalRecruitSite == 'WN'
        - 🎯 **자사**: 나머지 모든 공고
        
        **장점**
        - ✅ 불필요한 전체 탐색 제거로 속도 향상
        - ✅ 범위 확정 후 정확한 카운팅
        - ✅ 단계별 진행 상황 표시
        """)

    # 전체 공고 분석
    if (hasattr(st.session_state, 'run_analysis') and
            st.session_state.run_analysis):
        results = analyzer.comprehensive_job_analysis('ALL')
        if results:
            render_dashboard(results, "전체 공고 분석 결과")
        st.session_state.run_analysis = False

    # 오늘 공고 분석
    if (hasattr(st.session_state, 'check_today') and
            st.session_state.check_today):
        results = analyzer.comprehensive_job_analysis('TODAY')
        if results:
            render_dashboard(results, "오늘 등록된 공고 분석 결과")
        st.session_state.check_today = False

    # 지역별 분석
    if (hasattr(st.session_state, 'run_regional_analysis') and
            st.session_state.run_regional_analysis):
        region_code = st.session_state.selected_region_code
        region_name = REGION_CODES[region_code]
        period = st.session_state.selected_regional_period

        results = regional_analyzer.analyze_regional_jobs(
            region_code, region_name, period, max_pages=3
        )
        if results:
            render_regional_dashboard(results)
        st.session_state.run_regional_analysis = False

    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
    <small>
    채용공고 API를 활용한 공고 모니터링 대시보드 | 데이터 업데이트: 실시간
    </small>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()