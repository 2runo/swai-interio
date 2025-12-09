# Backend
## 1. Setup
```
pip install -r requirements.txt
```

## 2. 실행
```
uvicorn backend.main:app --port 8001
# 실행 후 비밀번호 입력해야 함.
```

* 실행 후 비밀번호를 입력해야 합니다. 비밀번호는 과제 제출 form에 github url과 함께 적어두었습니다.

# Frontend
## 1. 실행
```
python -m http.server --port 8000
# 실행 후 http://localhost:8000 접속
```

-> `http://localhost:8000` 접속하면 정상 작동할 것입니다.

# 주의사항
* 유료 opeani, openrouter api를 호출하므로 너무 많은 테스트는 자제 부탁드립니다.
