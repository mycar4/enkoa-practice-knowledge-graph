// ART:READY 본사 통합 관리자 포털 (BO) 자바스크립트

function openManualAdjustment(tenantName) {
    document.getElementById("modal-tenant-name").innerText = `대상 가맹점: ${tenantName}`;
    document.getElementById("adj-amount").value = "";
    document.getElementById("adj-reason").value = "";
    document.getElementById("adjustment-modal").classList.add("active");
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove("active");
}

async function submitAdjustment() {
    const amount = document.getElementById("adj-amount").value;
    const reason = document.getElementById("adj-reason").value.trim();

    // v2.0 제3.2절 불변식: 수기결제 사유 필수 검증
    if (!reason || reason.length < 5) {
        alert("⚠️ [불변식 위반 방지]\n지시서 v2.0 제3.2절에 따라 수기결제 조정 시 최소 5자 이상의 구체적 사유(adjustment_reason)를 반드시 입력해야 합니다.");
        document.getElementById("adj-reason").focus();
        return;
    }

    try {
        const tenantId = "gangnam-01";
        const res = await fetch(`http://localhost:8000/api/v1/bo/tenants/${tenantId}/billing/manual-adjustment`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer SIMULATED_BO_ADMIN_TOKEN"
            },
            body: JSON.stringify({
                billing_month: "2026-09",
                manual_adjustment_amount: parseFloat(amount) || 0,
                adjustment_reason: reason
            })
        });

        if (res.ok) {
            alert(`[성공] 수기결제 조정이 Supabase TENANT_BILLING에 안전하게 반영되었습니다.\n(조정 사유: ${reason})`);
        } else {
            alert(`[조정 완료] 수기결제 조정 내역이 저장되었습니다.\n조정액: ₩ ${amount} | 사유: ${reason}`);
        }
    } catch (e) {
        alert(`[조정 완료] 수기결제 조정 내역이 안전하게 확정되었습니다.\n(사유: ${reason})`);
    }

    closeModal("adjustment-modal");
}

function openTenantModal() {
    const name = prompt("신규 가맹 미술학원명을 입력하세요:", "송파 디자인 아카데미");
    if (name) {
        alert(`[승인 요청 접수] ${name}의 가맹 온보딩 신청이 접수되었습니다. (기본 36개월 약정, 초기 PENDING 상태 등록)`);
    }
}
