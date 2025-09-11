# 🤖 GitHub Actions 자동화 설정 가이드

## 개요
매일 한국시간 10시에 자동으로 알바몬 공고 분석을 실행하고 이메일로 리포트를 받을 수 있습니다.

## 🔧 설정 방법

### 1. GitHub Secrets 설정
GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret

다음 5개의 시크릿을 추가하세요:

#### 📧 이메일 설정 (Gmail 기준)
- `SMTP_SERVER`: `smtp.gmail.com`
- `SMTP_PORT`: `587`
- `SENDER_EMAIL`: `your-email@gmail.com` (발송자 이메일)
- `SENDER_PASSWORD`: `your-app-password` (Gmail 앱 비밀번호)
- `RECEIVER_EMAIL`: `receiver@gmail.com` (수신자 이메일)

#### Gmail 앱 비밀번호 생성 방법
1. Google 계정 → 보안 → 2단계 인증 활성화
2. 보안 → 앱 비밀번호 생성
3. 생성된 16자리 비밀번호를 `SENDER_PASSWORD`에 입력

### 2. 다른 이메일 서비스 사용 시

#### Naver 메일
- `SMTP_SERVER`: `smtp.naver.com`
- `SMTP_PORT`: `587`

#### Outlook/Hotmail
- `SMTP_SERVER`: `smtp-mail.outlook.com`
- `SMTP_PORT`: `587`

### 3. 자동 실행 확인
- 설정 완료 후 매일 한국시간 10시에 자동 실행
- GitHub → Actions 탭에서 실행 상태 확인 가능
- 수동 실행: Actions → Daily Job Analysis Report → Run workflow

## 📊 리포트 내용

### 이메일 리포트 포함 내용
1. **HTML 형식의 아름다운 리포트**
   - 전체 공고 분석 결과
   - 오늘 등록 공고 분석 결과
   - 소스별 분포 및 비율
   - 페이지 범위 정보

2. **JSON 첨부파일**
   - 상세한 분석 데이터
   - 페이지별 공고 수
   - API 요청 통계

### 분석 항목
- **전체 공고**: 모든 공고 현황
- **오늘 공고**: 당일 등록된 공고만
- **소스별 분류**: 자사/잡코리아/워크넷
- **페이지 범위**: 각 소스의 시작/끝 페이지
- **처리 시간**: 분석 소요 시간

## 🔄 실행 주기 변경

`.github/workflows/daily-report.yml` 파일의 cron 설정 수정:

```yaml
schedule:
  # 매일 10시 → 매일 9시
  - cron: '0 0 * * *'  # UTC 00:00 = 한국시간 09:00
  
  # 매일 → 평일만
  - cron: '0 1 * * 1-5'  # 월~금요일만
  
  # 매일 → 주 1회 (월요일)
  - cron: '0 1 * * 1'  # 매주 월요일
```

## 🚨 문제 해결

### 이메일이 안 옴
1. GitHub Secrets 설정 확인
2. Gmail 앱 비밀번호 재생성
3. Actions 탭에서 오류 로그 확인

### 분석 실패
1. 알바몬 API 변경 가능성
2. 네트워크 연결 문제
3. 코드 오류 - Issues 탭에 리포트

### 실행 시간 변경
- UTC 시간 기준으로 설정
- 한국시간 = UTC + 9시간
- 한국시간 10시 = UTC 1시

## 💡 추가 기능

### 수동 실행
- GitHub Actions 탭 → Daily Job Analysis Report
- "Run workflow" 버튼 클릭
- 즉시 분석 실행 및 이메일 발송

### 결과 파일 다운로드
- Actions → 완료된 실행 → Artifacts
- job-analysis-results.zip 다운로드
- JSON 형태의 상세 데이터 확인

## 📈 사용량 정보

### GitHub Actions 무료 한도
- **Public 저장소**: 무제한
- **Private 저장소**: 월 2000분
- **예상 사용량**: 월 90분 (여유 충분)

### 비용 절약 팁
- 저장소를 Public으로 설정 (무제한 사용)
- 불필요한 실행 주기 줄이기
- 오류 발생 시 빠른 수정

## 🔒 보안 주의사항

### GitHub Secrets 보안
- ✅ 이메일 비밀번호는 절대 코드에 직접 입력 금지
- ✅ GitHub Secrets에만 저장
- ✅ 앱 비밀번호 사용 (계정 비밀번호 아님)

### API 사용 주의
- ✅ 적절한 딜레이 설정 (현재 5초)
- ✅ 과도한 요청 방지
- ✅ 다양한 IP에서 분산 요청

---

## 📞 지원

문제가 발생하면 GitHub Issues에 상세한 오류 내용과 함께 문의해주세요.

**Happy Automation! 🚀**