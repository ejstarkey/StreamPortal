function fitOverlay() {
  const cont = document.querySelector('.scoring-container');
  const wrap = document.querySelector('#players-wrap');
  if (!cont || !wrap) return;
  const scale = cont.clientWidth / wrap.scrollWidth;
  wrap.style.transformOrigin = 'left bottom';
  wrap.style.transform = 'scale(' + scale + ')';
}

window.addEventListener('load', () => {
  fitOverlay();
  // Delay reload slightly after sizing settles
  setTimeout(() => location.reload(), 5000);
});
window.addEventListener('resize', fitOverlay);
