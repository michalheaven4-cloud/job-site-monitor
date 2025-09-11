#  모니터링 대시보드

워크넷과 잡코리아 연동 공고 현황을 실시간으로 모니터링하는 Streamlit 웹 애플리케이션입니다.

## 📋 주요 기능

### 🔍 전체 공고 분석 (`streamlit_app.py`)
- 워크넷/잡코리아 공고 수 정확한 계산
- 페이지별 시작점 자동 탐지
- 유료/무료 공고 구분 (알바몬 자사 공고)
- 실시간 디버깅 모드

### 🏙️ 지역별 공고 분석 (`regional_analyzer.py`)
- 17개 시도별 공고 현황 분석
- 무료/유료 공고 비율 계산
- 지역별 외부 연동 공고 현황
- 샘플링 기반 효율적 분석

## 🚀 설치 및 실행

### 1. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 애플리케이션 실행

#### 전체 공고 분석
```bash
streamlit run streamlit_app.py
```

#### 지역별 공고 분석  
```bash
streamlit run regional_analyzer.py
```

#### 특정 페이지 테스트
```bash
python test_page_1340.py
```

### 3. 웹 브라우저에서 접속
- 로컬: http://localhost:8501 (또는 8502)
- 자동으로 브라우저가 열립니다

## 📊 분석 알고리즘

### 공고 소스 분류
- **자사 공고** (알바몬): 기본 공고
- **잡코리아**: `jobkoreaRecruitNo ≠ 0`
- **워크넷**: `externalRecruitSite = 'WN'`

### 유료/무료 공고 구분 (알바몬만)
- **무료 공고**: `paidService.totalProductCount = 0`
- **유료 공고**: `paidService.totalProductCount > 0`

### 지역 코드
| 코드 | 지역 | 코드 | 지역 |
|------|------|------|------|
| A000 | 서울 | J000 | 강원 |
| B000 | 경기 | K000 | 충북 |
| C000 | 인천 | L000 | 충남 |
| D000 | 광주 | M000 | 전북 |
| E000 | 대전 | N000 | 전남 |
| F000 | 울산 | O000 | 경북 |
| G000 | 세종 | P000 | 경남 |
| H000 | 부산 | Q000 | 제주 |
| I000 | 대구 | | |

## 🎯 사용 예시

### 전체 공고 분석
1. `streamlit run streamlit_app.py` 실행
2. "🔍 전체 공고 분석" 버튼 클릭
3. 실시간으로 워크넷/잡코리아 시작 페이지 탐지
4. 정확한 공고 수와 비율 확인

### 지역별 분석
1. `streamlit run regional_analyzer.py` 실행  
2. 사이드바에서 지역 선택 (예: 서울, 부산)
3. 분석할 페이지 수 선택 (샘플링 수준)
4. "🔍 지역별 분석 시작" 클릭
5. 해당 지역의 무료/유료 공고 비율 확인

## 📂 파일 구조

```
job-site-monitor/
├── streamlit_app.py          # 전체 공고 분석 메인 앱
├── regional_analyzer.py      # 지역별 공고 분석 앱  
├── test_page_1340.py         # API 테스트 스크립트
├── requirements.txt          # Python 패키지 의존성
├── README.md                # 프로젝트 문서
└── logs/                    # 로그 파일 저장 디렉토리
```

## 🔧 기술 스택

- **Python 3.8+**
- **Streamlit**: 웹 대시보드
- **Requests**: API 호출
- **Pandas**: 데이터 처리
- **Plotly**: 차트 시각화

## 📝 주의사항

- API 요청 간 0.1초 간격으로 레이트 리미팅
- 지역별 분석은 샘플링 방식으로 효율성 향상
- 디버깅 모드에서 실제 API 응답 구조 확인 가능
