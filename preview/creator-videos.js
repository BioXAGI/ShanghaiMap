'use strict';
(() => {
  const list = Array.from(document.querySelectorAll('#haishang .lead-video'));
  const controls = document.getElementById('creator-tools');
  const input = document.getElementById('creator-search');
  const count = document.getElementById('creator-count');
  if (!list.length || !controls || !input || !count) return;
  const labels = list.map(el => el.textContent.toLocaleLowerCase());
  input.addEventListener('input', () => {
    const terms = input.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    let visible = 0;
    list.forEach((el, i) => {
      el.hidden = !terms.every(term => labels[i].includes(term));
      visible += Number(!el.hidden);
    });
    count.textContent = visible ? visible + ' 条视频' : '没有找到匹配的视频';
  });
  controls.hidden = false;
})();
