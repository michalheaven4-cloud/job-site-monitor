#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily Job Report CLI Script
GitHub Actions에서 실행되는 자동화 스크립트
"""

import os
import sys
import json
import time
from datetime import datetime

# 이메일 관련 import (try-except로 안전하게)
try:
    import smtplib
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart  
    from email.mime.base import MimeBase
    from email import encoders
    EMAIL_AVAILABLE = True
except ImportError as e:
    print(f"이메일 모듈 import 오류: {e}")
    EMAIL_AVAILABLE = False

# Streamlit 관련 import 제거하고 핵심 로직만 가져오기
import requests
import pandas as pd


class AlbamonAnalyzerCLI:
    """CLI 전용 알바몬 분석기 - Streamlit 의존성 제거"""
    
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

    def search_jobs(self, page=1, size=200, search_period_type='ALL'):
        """공고 검색 API 호출"""
        request_body = {
            "pagination": {
                "page": int(page),
                "size": int(size)
            },
            "recruitListType": "SEARCH",
            "sortTabCondition": {
                "searchPeriodType": str(search_period_type),
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
            print(f"API 요청 실패: {e}")
            return None

    def find_source_range_efficient(self, search_period_type='ALL'):
        """효율적인 범위 탐색 - CLI 버전 (로깅 제거)"""
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

        print(f"🚀 경계 기반 탐색: 전체 {total_count:,}개 공고 ({max_pages}페이지)")

        # 1단계: 워크넷 경계 찾기 (끝페이지부터)
        print("🔍 워크넷 경계 탐색 중...")
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
                    print(f"📍 워크넷 끝: {max_pages}페이지 ({worknet_count}개)")
        except Exception as e:
            print(f"끝페이지 확인 오류: {e}")

        # 워크넷이 있으면 시작점 찾기
        if worknet_end:
            for i, page in enumerate(range(max_pages, 0, -1)):
                try:
                    # 진행 상황 표시 (100페이지마다)
                    if page % 100 == 0:
                        progress = (i + 1) / max_pages * 100
                        remaining_pages = max_pages - i
                        print(f"🔍 워크넷 탐색: 페이지 {page} | 진행률: {progress:.1f}% | 남은: {remaining_pages}")
                    
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
                        print(f"✅ 워크넷 시작점 확정: {worknet_start}~{worknet_end}페이지")
                        break
                        
                    time.sleep(0.002)
                    
                except Exception as e:
                    print(f"페이지 {page} 검색 오류: {e}")
                    continue

        if worknet_start and worknet_end:
            print(f"✅ 워크넷: {worknet_start}~{worknet_end}페이지")
        else:
            print("📊 워크넷 공고 없음")

        # 2단계: 잡코리아 경계 찾기 (워크넷 앞쪽부터)
        print("🔍 잡코리아 경계 탐색 중...")
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
                        print(f"📍 잡코리아 끝: {search_start_page}페이지 ({jobkorea_count}개)")
            except Exception as e:
                print(f"잡코리아 끝페이지 확인 오류: {e}")

        # 잡코리아가 있으면 시작점 찾기
        if jobkorea_end:
            total_search_pages = search_start_page
            for i, page in enumerate(range(search_start_page, 0, -1)):
                try:
                    # 진행 상황 표시 (100페이지마다)
                    if page % 100 == 0:
                        progress = (i + 1) / total_search_pages * 100
                        remaining_pages = total_search_pages - i
                        print(f"🔍 잡코리아 탐색: 페이지 {page} | 진행률: {progress:.1f}% | 남은: {remaining_pages}")
                    
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
                        print(f"✅ 잡코리아 시작점 확정: {jobkorea_start}~{jobkorea_end}페이지")
                        break
                        
                    time.sleep(0.002)
                    
                except Exception as e:
                    print(f"페이지 {page} 검색 오류: {e}")
                    continue

        if jobkorea_start and jobkorea_end:
            print(f"✅ 잡코리아: {jobkorea_start}~{jobkorea_end}페이지")
        else:
            print("📊 잡코리아 공고 없음")

        # 3단계: 실제 확인한 개수 기반 계산 (추가 요청 없이)
        print("🔍 공고 수 계산 중...")
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
            print(f"📊 잡코리아: {jobkorea_start}~{jobkorea_end}페이지 (총 {total_jobkorea_count:,}개)")
        if worknet_start and worknet_end:
            print(f"📊 워크넷: {worknet_start}~{worknet_end}페이지 (총 {total_worknet_count:,}개)")
            
        print(f"⚡ 경계 탐색 완료: {search_duration:.2f}초, 총 {total_requests}번 요청")

        return jobkorea_start, jobkorea_end, worknet_start, worknet_end, total_count, jobkorea_counts, worknet_counts, search_duration

    def comprehensive_job_analysis(self, search_period_type='ALL'):
        """효율적인 범위 탐색으로 공고 분석 - CLI 버전"""
        try:
            print(f"🔍 {search_period_type} 공고 분석 시작...")
            result = self.find_source_range_efficient(search_period_type)
            jobkorea_start, jobkorea_end, worknet_start, worknet_end, total_count, jobkorea_counts, worknet_counts, search_duration = result

            if total_count == 0:
                return {
                    'total_count': 0,
                    'albamon_count': 0,
                    'jobkorea_count': 0,
                    'worknet_count': 0,
                    'search_duration': search_duration,
                    'analysis_type': search_period_type
                }

            # 정확한 공고 수 계산 (실제 페이지별 카운트 기반)
            jobkorea_count = sum(jobkorea_counts.values()) if jobkorea_counts else 0
            worknet_count = sum(worknet_counts.values()) if worknet_counts else 0
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
                'detailed_counts': {
                    'jobkorea_by_page': jobkorea_counts,
                    'worknet_by_page': worknet_counts
                },
                'search_duration': search_duration,
                'analysis_type': search_period_type,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"분석 중 오류 발생: {e}")
            return None


def format_report_html(all_result, today_result):
    """HTML 형식으로 리포트 생성"""
    
    def format_number(num):
        return f"{num:,}"
    
    def calculate_percentage(part, total):
        if total == 0:
            return "0.0"
        return f"{(part / total * 100):.1f}"
    
    # 현재 시간
    now = datetime.now()
    report_time = now.strftime("%Y년 %m월 %d일 %H시 %M분")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; margin-bottom: 20px; }}
            .section {{ margin: 20px 0; padding: 15px; border-radius: 8px; }}
            .all-jobs {{ background-color: #e8f5e8; border-left: 4px solid #4CAF50; }}
            .today-jobs {{ background-color: #e3f2fd; border-left: 4px solid #2196F3; }}
            .metrics {{ display: flex; justify-content: space-around; margin: 15px 0; }}
            .metric {{ text-align: center; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #333; }}
            .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
            .percentage {{ font-size: 14px; color: #888; }}
            .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
            .range-info {{ background-color: #f9f9f9; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 알바몬 공고 분석 리포트</h1>
                <p>{report_time} 자동 생성</p>
            </div>
    """
    
    # 전체 공고 분석 결과
    if all_result and all_result['total_count'] > 0:
        html_content += f"""
            <div class="section all-jobs">
                <h2>🌐 전체 공고 분석</h2>
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-value">{format_number(all_result['total_count'])}</div>
                        <div class="metric-label">전체 공고</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{format_number(all_result['albamon_count'])}</div>
                        <div class="metric-label">자사 공고</div>
                        <div class="percentage">{calculate_percentage(all_result['albamon_count'], all_result['total_count'])}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{format_number(all_result['jobkorea_count'])}</div>
                        <div class="metric-label">잡코리아</div>
                        <div class="percentage">{calculate_percentage(all_result['jobkorea_count'], all_result['total_count'])}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{format_number(all_result['worknet_count'])}</div>
                        <div class="metric-label">워크넷</div>
                        <div class="percentage">{calculate_percentage(all_result['worknet_count'], all_result['total_count'])}%</div>
                    </div>
                </div>
        """
        
        # 페이지 범위 정보
        if all_result.get('jobkorea_start_page') or all_result.get('worknet_start_page'):
            html_content += '<div class="range-info">'
            if all_result.get('jobkorea_start_page'):
                jk_range = f"{all_result['jobkorea_start_page']}~{all_result['jobkorea_end_page']}페이지"
                html_content += f"💼 잡코리아 범위: {jk_range}<br>"
            if all_result.get('worknet_start_page'):
                wn_range = f"{all_result['worknet_start_page']}~{all_result['worknet_end_page']}페이지"
                html_content += f"🏛️ 워크넷 범위: {wn_range}<br>"
            html_content += f"⏱️ 분석 시간: {all_result['search_duration']:.2f}초"
            html_content += '</div>'
        
        html_content += '</div>'
    
    # 오늘 공고 분석 결과
    if today_result and today_result['total_count'] > 0:
        html_content += f"""
            <div class="section today-jobs">
                <h2>📅 오늘 등록 공고 분석</h2>
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-value">{format_number(today_result['total_count'])}</div>
                        <div class="metric-label">전체 공고</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{format_number(today_result['albamon_count'])}</div>
                        <div class="metric-label">자사 공고</div>
                        <div class="percentage">{calculate_percentage(today_result['albamon_count'], today_result['total_count'])}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{format_number(today_result['jobkorea_count'])}</div>
                        <div class="metric-label">잡코리아</div>
                        <div class="percentage">{calculate_percentage(today_result['jobkorea_count'], today_result['total_count'])}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{format_number(today_result['worknet_count'])}</div>
                        <div class="metric-label">워크넷</div>
                        <div class="percentage">{calculate_percentage(today_result['worknet_count'], today_result['total_count'])}%</div>
                    </div>
                </div>
                <div class="range-info">
                    ⏱️ 분석 시간: {today_result['search_duration']:.2f}초
                </div>
            </div>
        """
    elif today_result and today_result['total_count'] == 0:
        html_content += """
            <div class="section today-jobs">
                <h2>📅 오늘 등록 공고 분석</h2>
                <p style="text-align: center; color: #666;">오늘 등록된 공고가 없습니다.</p>
            </div>
        """
    
    html_content += """
            <div class="footer">
                <p>🤖 GitHub Actions 자동 생성 리포트</p>
                <p>Job Site Monitor - Automated Daily Report</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content


def send_report_to_api(all_result, today_result):
    """API로 리포트 데이터 전송"""

    # 환경 변수에서 API 설정 가져오기
    api_url = os.getenv('REPORT_API_URL')
    api_password = os.getenv('REPORT_API_PASSWORD')

    if not api_url or not api_password:
        print("❌ API 설정이 완료되지 않았습니다.")
        print("필요한 환경 변수: REPORT_API_URL, REPORT_API_PASSWORD")
        print("\n=== 분석 결과 요약 ===")
        if all_result:
            print(f"전체 공고: {all_result['total_count']:,}개")
            print(f"- 자사: {all_result['albamon_count']:,}개")
            print(f"- 잡코리아: {all_result['jobkorea_count']:,}개")
            print(f"- 워크넷: {all_result['worknet_count']:,}개")
        if today_result:
            print(f"오늘 공고: {today_result['total_count']:,}개")
        return False

    try:
        # JSON 데이터 구성
        today = datetime.now().strftime("%Y-%m-%d")
        json_data = {
            'report_date': today,
            'all_result': all_result,
            'today_result': today_result,
            'generated_at': datetime.now().isoformat(),
            'source': 'github_actions'
        }

        # API 요청 헤더
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_password}'
        }

        # API 전송
        print(f"📡 API로 데이터 전송 중... {api_url}")

        response = requests.post(
            api_url,
            json=json_data,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        print("✅ API 전송 완료!")
        print(f"응답: {response.status_code}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ API 전송 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"응답 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🚀 알바몬 공고 분석 자동화 스크립트 시작")
    print("=" * 60)
    
    analyzer = AlbamonAnalyzerCLI()
    
    # 전체 공고 분석
    print("\n1️⃣ 전체 공고 분석 시작...")
    all_result = analyzer.comprehensive_job_analysis('ALL')
    
    if all_result:
        print(f"✅ 전체 공고 분석 완료: {all_result['total_count']:,}개")
        print(f"   - 자사: {all_result['albamon_count']:,}개")
        print(f"   - 잡코리아: {all_result['jobkorea_count']:,}개") 
        print(f"   - 워크넷: {all_result['worknet_count']:,}개")
    else:
        print("❌ 전체 공고 분석 실패")
        return 1
    
    # 잠시 대기 (API 부하 방지)
    print("\n⏸️ API 부하 방지를 위해 5초 대기...")
    time.sleep(5)
    
    # 오늘 공고 분석
    print("\n2️⃣ 오늘 공고 분석 시작...")
    today_result = analyzer.comprehensive_job_analysis('TODAY')
    
    if today_result:
        print(f"✅ 오늘 공고 분석 완료: {today_result['total_count']:,}개")
        if today_result['total_count'] > 0:
            print(f"   - 자사: {today_result['albamon_count']:,}개")
            print(f"   - 잡코리아: {today_result['jobkorea_count']:,}개")
            print(f"   - 워크넷: {today_result['worknet_count']:,}개")
        else:
            print("   - 오늘 등록된 공고 없음")
    else:
        print("❌ 오늘 공고 분석 실패")
        return 1
    
    # API 전송
    print("\n3️⃣ API 리포트 전송 시작...")
    api_success = send_report_to_api(all_result, today_result)

    if api_success:
        print("✅ 모든 작업 완료!")
        return 0
    else:
        print("⚠️ 분석은 완료되었으나 API 전송 실패")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)