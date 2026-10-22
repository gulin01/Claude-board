# Agent Board

[English](README.md) · **한국어**

**모든 Claude 에이전트를 한눈에.** Claude Code 세션(터미널, 데스크톱 앱, IDE)마다 작은 캐릭터가 하나씩 생겨요.
손을 흔들면 = 확인이 필요해요, 타자를 치면 = 작업 중, ✓ = 완료, 땀을 흘리면 = 너무 커져서 새로 시작하는 게 좋아요.

**이 컴퓨터에서만** 동작하고, 아무것도 밖으로 보내지 않아요. **macOS**와 **Windows**에서 쓸 수 있어요.

> **가장 쉬운 방법: Claude에게 맡기기.** 저장소를 내려받고 그 폴더에서 Claude Code를 연 다음
> *"Agent Board 설치해 줘"* 라고 말하세요. Claude가 [CLAUDE.md](CLAUDE.md)를 읽고 질문한 뒤 설치해 줘요.

## 내 정보는 어디에 저장되나요
이 폴더에는 **코드만** 있어요. 설정(언어, 계정)과 데이터(기록, 휴지통, 사용량)는 따로 있는 폴더에 저장돼요:
**macOS** `~/.agent-board/` · **Windows** `C:\Users\<사용자>\.agent-board\`.
이 폴더에 개인 정보가 들어가는 일은 없어요.

## 설치 (Mac, 5분)

### 1. 필요한 것
| 필요한 것 | 확인 방법 | 없으면 |
|---|---|---|
| Mac | | |
| Claude Code (로그인 상태) | `claude --version` | https://docs.anthropic.com/claude-code 설치 후 `claude` 실행해서 로그인 |
| Python 3.9 이상 | `python3 --version` | `xcode-select --install` |
| Xcode 명령줄 도구 *(권장)* | `swiftc --version` | `xcode-select --install` (앱 창, 알림, 메뉴 막대 버디에 필요) |
| Google Chrome *(선택)* | | Chrome 탭 찾기에만 필요 |

### 2. 내려받기
```bash
git clone -b work https://github.com/gulin01/Claude-board.git ~/agent-board
cd ~/agent-board
```

### 3. 설치하기
```bash
python3 setup.py
```
처음에 **Language / 언어** 에서 `2` (한국어)를 고르세요. 그다음 Chrome 프로필마다 Claude를 쓰는지 물어봐요.

나머지는 자동으로 설치돼요: Claude Code 연결(기존 설정은 그대로 두고 백업해요), **Agent Board** 앱,
메뉴 막대 버디, 로그인할 때 자동 시작, 바탕화면 바로가기.

### 4. macOS 알림창 두 개 허용
- **"Agent Board에서 알림을 보내려고 합니다"** → **허용**. 팁: 시스템 설정 → 알림 → Agent Board →
  **지속적**으로 바꾸면 닫을 때까지 남아 있어요.
- **"python3이 Google Chrome을 제어하려고 합니다"** → **확인** (탭 찾기용이에요. 페이지 내용은 읽지 않아요).

### 5. 선택: Chrome 탭 찾기 (Chrome 프로필마다 클릭 3번)
보드에서 열린 Chrome 탭을 찾고 바로 이동할 수 있어요. 설치 프로그램이 페이지와 폴더를 열어 줘요:
1. Chrome에서 `chrome://extensions` 열기
2. 오른쪽 위 **개발자 모드** 켜기
3. **압축해제된 확장 프로그램을 로드합니다** → 이 프로젝트 안의 **`extension`** 폴더 선택

쓰는 Chrome 프로필마다 한 번씩 해 주세요 (Google 계정마다 확장 프로그램이 따로 있어요).

### 6. 선택: Claude 데스크톱 채팅 (커넥터)
Claude 데스크톱 **채팅** 대화는 보드가 읽을 수 있는 곳에 저장되지 않아서, 설치 프로그램이 대신 작은
**Agent Board 커넥터**를 Claude 데스크톱에 추가해요. 그러면 채팅 속 Claude가 긴 작업을 보드에 보여 주고
(작업 중 → 완료, 알림 포함) *"에이전트들 뭐 하고 있어?"* 에도 답할 수 있어요.
- 설치 후 **Claude 데스크톱을 다시 시작**하세요. Claude가 커넥터를 처음 쓸 때 **항상 허용**을 고르세요.
- 이 컴퓨터의 보드하고만 통신해요. 커넥터를 추가하기 전의 예전 채팅은 보이지 않아요.

### 7. Claude Code 다시 시작
열려 있는 Claude Code 세션을 닫았다가 다시 여세요. 이제 바탕화면의 **Agent Board** 를 열면 돼요.

> 나중에 답변 바꾸기: `python3 setup.py` 를 다시 실행하거나 `~/.agent-board/config.json` 을 수정하세요.
> 바뀌는 것 없이 미리보기: `python3 setup.py --dry-run`

## Windows

Mac과 같은 보드, 캐릭터, 사용량을 써요. 질문도 같아요.

1. **설치** (없다면):
   - Windows용 [Claude Code](https://docs.anthropic.com/claude-code) (로그인), [Git for Windows](https://git-scm.com/download/win)
   - [Python 3.9+](https://www.python.org/downloads/windows/) — 설치할 때 **"Add python.exe to PATH"** 를 꼭 체크하세요
2. **내려받기** (PowerShell):
   ```
   git clone -b work https://github.com/gulin01/Claude-board.git $HOME\agent-board
   cd $HOME\agent-board
   ```
3. **설치**: `py setup.py` → 언어에서 `2` (한국어) 선택
4. **Claude Code 다시 시작** 후 바탕화면의 **Agent Board** 열기 (Chrome/Edge 앱 창으로 열려요)

| | macOS | Windows |
|---|---|---|
| 보드, 캐릭터, 사용량 | ✅ | ✅ |
| 알림 (누르면 해당 에이전트 열기) | ✅ Agent Board 앱 | ✅ Windows 알림 (*Windows PowerShell* 이름으로 표시) |
| 로그인할 때 자동 시작 | ✅ | ✅ 시작프로그램 폴더 |
| 시계 옆 버디 | ✅ 메뉴 막대 | ✅ 작업 표시줄 트레이 (오른쪽 아래) |
| Chrome 탭 찾기 | ✅ | ✅ Chrome 확장 프로그램으로 (5단계) |

알림이 안 오면: 설정 → 시스템 → 알림 → **Windows PowerShell** 켜기.
트레이 버디가 안 보이면: 시계 옆 **^** 화살표를 눌러 버디를 작업 표시줄로 끌어오세요.


## 매일 쓰기
- **바탕화면의 "Agent Board"** 를 열거나 http://127.0.0.1:4317 에 접속하세요. 로그인하면 자동으로 켜져요.
- **에이전트를 누르면** 한 일과 다음 할 일이 보여요: 미리보기 열기, Chrome 탭으로 이동, 이어서 하기, 새로 시작.
- **빨간 배터리** = 대화(컨텍스트)가 너무 커져서 메시지마다 비용이 커요. 작업을 마친 뒤 **새로 시작** 을 누르면
  요약이 복사돼요. 새 세션에 붙여 넣고 예전 에이전트는 삭제하세요.
- **메뉴 막대 / 트레이 버디**는 확인이 필요하면 주황색으로 바뀌고 손을 흔들어요.
- **더보기 ⋯** 에 테마(자동 / 밝게 / 어둡게), 언어(자동 / English / 한국어), TV 모드, 소리, 휴지통이 있어요.

## 문제가 생기면
| 문제 | 해결 |
|---|---|
| 보드가 비어 있어요 | Claude Code를 한 번 쓰고 몇 초 기다리세요 |
| 알림이 안 와요 | Mac: 시스템 설정 → 알림 → Agent Board 허용. Windows: Windows PowerShell 알림 켜기. Claude Code 세션 다시 시작 |
| 5시간/주간 사용량이 안 보여요 | Claude Code에서 메시지를 한 번 보내세요 (상태 표시줄에서 가져와요) |
| 보드 페이지가 안 열려요 | 설치를 다시 실행하거나 직접 시작: `python3 server.py` (Windows: `py server.py`) |

## 제거
```bash
python3 setup.py --uninstall     # 연결, 자동 시작, 바탕화면 바로가기를 지워요. 데이터는 남아요
```

더 자세한 내용(알림 규칙, 쉬는 에이전트 정리, 사용량 패널 등)은 [English README](README.md#reference)의 Reference를 보세요.
