// ART:READY 학생·학부모 포털 (FO) 자바스크립트

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initRoleSwitch();
    loadPolicies();
});

// 1. 탭 네비게이션 전환
function initTabs() {
    const tabBtns = document.querySelectorAll(".tab-btn");
    const panes = document.querySelectorAll(".tab-pane");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            panes.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const targetId = `pane-${btn.dataset.tab}`;
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add("active");
            }
        });
    });
}

// 2. 학생 뷰 vs 학부모 뷰 스위치 (RBAC 시뮬레이션)
function initRoleSwitch() {
    const roleBtns = document.querySelectorAll(".role-btn");
    const userDisplay = document.getElementById("user-display");
    const guardianBox = document.getElementById("guardian-box");

    roleBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            roleBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            const role = btn.dataset.role;
            if (role === "PARENT") {
                userDisplay.textContent = "박현숙 학부모님 (보호자 모드 - Read Only)";
                guardianBox.style.display = "none"; // 학부모 뷰에서는 연동코드 숨김
            } else {
                userDisplay.textContent = "김예원 원생 (강남본원)";
                guardianBox.style.display = "block";
            }
        });
    });
}

// 3. 학부모 연동 코드 복사
function copyCode() {
    const codeText = document.getElementById("guardian-code").innerText;
    navigator.clipboard.writeText(codeText).then(() => {
        alert(`학부모 연동 코드 [${codeText}]가 클립보드에 복사되었습니다.\n학부모님 가입 시 전달해 주세요.`);
    });
}

// 4. 비공개 버킷 서명 URL 발급 요청 (보안 시뮬레이션)
async function requestSignedUrl(filePath) {
    try {
        const res = await fetch("https://adminartreadykr.vercel.app/api/v1/storage/signed-url", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer SIMULATED_TOKEN"
            },
            body: JSON.stringify({
                file_path: filePath,
                expires_in: 3600
            })
        });
        
        if (res.ok) {
            const data = await res.json();
            alert(`[보안 검증 완료] 1시간 유효 서명 URL이 발급되었습니다:\n${data.signed_url}`);
        } else {
            alert(`[안내] Supabase Storage 버킷 'art-franchise-private' 설정이 필요합니다.\n임시 보안 토큰이 적용된 상태입니다.`);
        }
    } catch (e) {
        alert(`[보안 알림] 백엔드 API 서버가 기동 중일 때 실시간 Signed URL 발급이 연동됩니다.`);
    }
}

// 5. 활성 정책 문서 로드 (Supabase REST API 직접 조회)
async function loadPolicies() {
    const container = document.getElementById("policy-content");
    const supabaseUrl = "https://jqdtqawrkdidcdfzxzwb.supabase.co";
    const anonKey = "sb_publishable_m3si3M17RpGHrIXt8Au9tQ_w3CwtCpW";

    try {
        const res = await fetch(`${supabaseUrl}/rest/v1/policy_documents?is_active=eq.true&select=*`, {
            headers: {
                "apikey": anonKey,
                "Authorization": `Bearer ${anonKey}`
            }
        });

        if (res.ok) {
            const policies = await res.json();
            if (policies.length === 0) {
                container.innerHTML = `
                    <div class="feedback-box">
                        <strong>📌 현재 공시된 정책</strong>
                        <p><strong>[공시 대기]</strong> 본사 관리자(BO)가 현재 이용약관 및 개인정보처리방침 v2.0 정식 게재를 준비 중입니다. (만 14세 미만 아동보호법 제22조의2 조항 및 학생 실기작품 비공개 스토리지 정책 자동 적용)</p>
                    </div>
                `;
            } else {
                let html = "";
                policies.forEach(p => {
                    html += `
                        <div class="feedback-box" style="margin-bottom: 12px;">
                            <strong>${p.doc_type} (v${p.version})</strong>
                            <p>${p.content}</p>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
        }
    } catch (e) {
        container.innerHTML = "<p class='text-muted'>정책 문서를 불러오는 중 오류가 발생했습니다.</p>";
    }
}
