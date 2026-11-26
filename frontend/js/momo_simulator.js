/* FitFlow: clearly-labelled classroom payment provider simulator.
 * No MoMo account login, OTP, PIN, bank credentials or real transfers.
 * Server owns state; this file only renders public sample details and posts explicit demo actions.
 */
'use strict';
(() => {
  const el=id=>document.getElementById(id);
  const json=el('momo-data');
  if(!json){return;}
  let data;
  try{data=JSON.parse(json.textContent)}catch{return}
  const amount=Number(data.amount||0).toLocaleString('vi-VN')+'đ';
  const isAuth=data.kind==='authorization';
  const pending=isAuth?data.status==='PENDING_DEMO':data.status==='PENDING';
  const success=isAuth?data.status==='ACTIVE_DEMO':data.status==='PAID';
  const returnUrl=data.return_url||'/';
  el('back-link').href=returnUrl;
  el('return-button').href=returnUrl;
  el('clock').textContent=new Date().toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit',hour12:false});
  el('invoice').textContent=data.invoice||'FF-00000';
  el('description').textContent=isAuth?'Liên kết Ví MoMo và cho phép tự động gia hạn Monthly Pass':'Thanh toán gói tập Monthly Pass FitFlow Club';
  el('invoice-amount').textContent=amount;
  el('term-amount').textContent=amount;
  el('consent-amount').textContent=amount;
  el('total-money').textContent=amount;
  el('wallet-detail').textContent=isAuth?'Ví mẫu · •••• 8842':'Số dư mẫu: 4.051.666đ';
  el('approve-form').action=data.primary_action||'#';
  el('decline-form').action=data.decline_action||'#';
  el('auth-details').hidden=!isAuth;
  el('auth-entry').hidden=!(isAuth&&pending);
  // These inputs are associated with approve-form even when their parent is hidden.
  // Disable both for a payment-only checkout, otherwise native HTML validation
  // silently blocks the Confirm button despite no visible input on the page.
  for (const id of ['wallet-suffix','auth-consent']) {
    const field=el(id);
    field.disabled=!(isAuth&&pending);
    field.required=isAuth&&pending;
  }
  el('bank-section').hidden=isAuth||!pending;
  el('amount-label').textContent=isAuth?'Giới hạn mỗi tháng':'Tạm tính';
  el('sources-heading').textContent=isAuth?'Xác nhận ví và ủy quyền':'Phương thức thanh toán';
  el('total-title').textContent=isAuth?'Giới hạn mỗi tháng':'Tổng tiền';
  el('terms-message').textContent=isAuth?
    'Bạn chỉ đang cấp quyền thu định kỳ. Khoản thanh toán tháng đầu sẽ được xác nhận riêng.':
    'Thanh toán tháng đầu cho gói hội viên. Các kỳ sau có thể được thu theo ủy quyền đã cấp.';
  el('banner-title').textContent=isAuth?'Xác nhận liên kết Ví MoMo':'Bạn đang xác nhận thanh toán trên MoMo';
  el('banner-desc').textContent=isAuth?'Cho phép FitFlow yêu cầu thu phí Monthly Pass hàng tháng':'Đơn hàng FitFlow Club · Đã cấp quyền MoMo Auto-Renew';
  el('primary-label').textContent=isAuth?'Cho phép thu định kỳ':'Xác nhận';
  el('decline-button').textContent=isAuth?'Từ chối liên kết ví':'Từ chối thanh toán';
  el('dock-caption').textContent='Classroom simulator · Không chuyển tiền hoặc liên kết tài khoản thật.';

  const offers=el('offers');
  offers.addEventListener('click',()=>{
    const expanded=offers.getAttribute('aria-expanded')==='true';
    offers.setAttribute('aria-expanded',String(!expanded));
    el('offer-note').hidden=expanded;
  });

  if(!pending){
    el('approve-form').hidden=true;
    el('decline-form').hidden=true;
    el('return-button').hidden=false;
    el('result-message').hidden=false;
    el('result-message').className='result-message '+(success?'positive':'negative');
    el('result-message').innerHTML=success?(
      isAuth?'<h3>Liên kết ví thành công</h3><p>Quyền thu định kỳ đã được cấp trong bản mô phỏng.</p>':
      '<h3>Thanh toán thành công</h3><p>FitFlow đã ghi nhận hóa đơn được thanh toán.</p>'
    ):(isAuth?
      '<h3>Chưa cấp quyền thu định kỳ</h3><p>Bạn đã từ chối. FitFlow sẽ không thu tự động nếu chưa có quyền hợp lệ.</p>':
      '<h3>Thanh toán không thành công</h3><p>Bạn có thể quay lại FitFlow và chọn phương thức VietQR để thanh toán hóa đơn chưa trả.</p>');
    el('terms-summary').hidden=true;
    el('bank-section').hidden=true;
    el('auth-entry').hidden=true;
    el('auth-details').hidden=true;
    el('total-money').textContent=amount;
    if(success && !isAuth){
      document.querySelector('.header-title').textContent='Chi Tiết Giao Dịch';
      el('success-screen').hidden=false;
      el('success-amount').textContent='-'+amount;
      el('success-invoice').textContent=data.invoice||'FF-00000';
      el('success-reference').textContent=data.transaction_reference||'N/A';
      el('success-member').textContent=data.member_name||'Hội viên FitFlow';
      el('success-plan').textContent=data.plan_name||'Monthly Pass';
      el('success-membership-until').textContent=data.membership_until ? new Date(data.membership_until).toLocaleDateString('vi-VN') : 'Xem tại FitFlow';
      el('manage-fitflow-link').href=returnUrl;
      const paidDate = data.paid_at ? new Date(data.paid_at) : null;
      el('success-date').textContent=paidDate && !Number.isNaN(+paidDate)
        ? paidDate.toLocaleString('vi-VN',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})
        : 'Đã ghi nhận';
      el('sim-scroll').scrollTop=0;
      document.body.classList.add('is-payment-success');
      el('info-banner').hidden=true;
      el('merchant-card').hidden=true;
      el('offers').hidden=true;
      el('sources-card').hidden=true;
      document.querySelector('.total-row').hidden=true;
      el('dock-caption').textContent='Xem biên nhận và thẻ hội viên tại FitFlow.';
      el('success-funding').textContent='Ví MoMo · mẫu';
      el('support-summary').textContent=`FitFlow Club · ${data.invoice||''} · ${data.transaction_reference||''} · ${amount} · ${data.member_name||''}`;
      el('result-message').hidden=true;
    }
  }


// All post-payment actions stay in the current phone/tab.
const copyText=async value=>{
  if(!value)return false;
  try{await navigator.clipboard.writeText(value);return true}
  catch{
    try{const input=document.createElement('textarea');input.value=value;input.style.position='fixed';input.style.opacity='0';document.body.appendChild(input);input.select();const ok=document.execCommand('copy');input.remove();return ok}catch{return false}
  }
};
document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{
  const target=el(button.dataset.copy);
  const original=button.textContent;
  const ok=await copyText(target?.textContent?.trim());
  button.textContent=ok?'✓':'!';
  window.setTimeout(()=>button.textContent=original,1400);
}));
const toggle=el('transaction-process-toggle');
toggle?.addEventListener('click',()=>{
  const show=toggle.getAttribute('aria-expanded')!=='true';
  toggle.setAttribute('aria-expanded',String(show));
  el('transaction-process-panel').hidden=!show;
});
const support=el('support-sheet');
el('contact-support-button')?.addEventListener('click',()=>{support.hidden=false;el('support-close').focus();});
el('support-close')?.addEventListener('click',()=>{support.hidden=true;el('contact-support-button').focus();});
el('support-copy')?.addEventListener('click',async()=>{
  const copied=await copyText(el('support-summary').textContent);
  el('support-feedback').textContent=copied?'Đã sao chép thông tin giao dịch.':'Trình duyệt không cho sao chép. Bạn có thể chọn và sao chép nội dung bên trên.';
});
window.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&!support.hidden){support.hidden=true;el('contact-support-button').focus()}});

  if(!isAuth&&pending){
    // Sample funding source selection: simulation only, never initiates a bank debit.
    const options=[...document.querySelectorAll('input[name="ui-source"]')];
    options.forEach(input=>{
      input.addEventListener('change',()=>{
        el('funding-source').value=input.value;
        document.querySelectorAll('.funding-source,.wallet-source').forEach(node=>node.classList.remove('is-selected'));
        input.closest('label')?.classList.add('is-selected');
      });
    });
  }
  for(const id of ['approve-form','decline-form']){
    const form=el(id);
    form.addEventListener('submit',()=>{
      const button=form.querySelector('button');
      if(button){button.disabled=true;button.textContent='Đang xử lý…'}
    });
  }
})();
