# GitHub Actions 자동 배포용 프롬프트 (템플릿)

이 프로젝트의 **원격 쿠버네티스(Remote K8s) 자동 배포** 방식을 다른 프로젝트에 적용할 때 사용할 수 있는 가이드입니다.

---

## 1. AI에게 전달할 프롬프트 (복사해서 사용)

> **[프롬프트 시작]**
> `xrpaout` 프로젝트의 배포 방식을 참고하여, 현재 프로젝트를 GitHub에 `push`하면 **원격 서버의 쿠버네티스**에 자동 배포되도록 GitHub Actions 워크플로우를 만들어줘.
> 
> **현재 프로젝트 정보:**
> - **프로젝트 이름:** [예: My-New-App]
> - **이미지 이름:** [예: my-app-backend, my-app-frontend]
> - **원격 서버 IP:** [예: 192.168.0.22]
> 
> **요구사항:**
> 1. **Runner:** 로컬망의 **Self-hosted runner**를 사용해.
> 2. **빌드 및 전송:** Docker 이미지를 빌드한 뒤, `docker save`로 TAR 파일을 만들고 `pscp.exe`를 사용해 원격 서버로 전송해.
> 3. **원격 배포:** `plink.exe`를 사용해 원격 서버에서 이미지를 `docker load`하고, `kubectl apply`를 수행해.
> 4. **서비스 노출:** 배포 후 `screen`을 사용해 `kubectl port-forward`를 백그라운드에서 실행하여 외부 접속 포트를 확보해줘.
> 5. **태그 관리:** Git Commit SHA를 사용하여 매 배포마다 고유한 이미지 태그를 생성하고 YAML을 업데이트해줘.
> **[프롬프트 끝]**

---

## 2. 필수 구성 요소 및 수정 항목

### ① `.github/workflows/deploy.yml`
- **`$PW`**: 서버 접속 비밀번호 (GitHub Secrets 사용 권장).
- **`pscp/plink 경로`**: PuTTY 설치 경로 확인 (보통 `C:\Program Files\PuTTY\`).
- **`RemoteCmd`**: 원격 서버에서 실행할 일련의 명령(load -> sed -> apply -> rollout -> port-forward).

### ② `k8s/manifests.yaml`
- **`imagePullPolicy: Never`**: 원격 서버 로컬 이미지를 사용하므로 반드시 `Never`로 설정.
- **`NodePort`**: 서비스 타입 및 포트 번호 확인.

### ③ 원격 서버 환경
- **Docker & kubectl**: 원격 서버에 설치되어 있어야 함.
- **GNU Screen**: 백그라운드 포트 포워딩을 위해 `screen` 설치 권장.

---

## 3. 트러블슈팅 가이드

1. **디스크 꽉 참**: `minikube status`에서 `InsufficientStorage`가 뜨면 `docker system prune -f`를 실행하세요.
2. **접속 불가**: 서버에서 `netstat -tuln | grep [포트]`를 통해 포트 포워딩 프로세스가 살아있는지 확인하세요.
3. **권한 오류**: `plink` 사용 시 첫 접속이라면 `known_hosts`에 등록되어야 합니다.

