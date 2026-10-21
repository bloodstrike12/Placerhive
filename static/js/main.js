document.addEventListener('DOMContentLoaded',()=>{
 const btn=document.querySelector('.mobile-menu-btn');
 const links=document.querySelector('.nav-links');
 if(btn&&links){btn.addEventListener('click',()=>{const open=links.classList.toggle('open');btn.setAttribute('aria-expanded',open?'true':'false');btn.textContent=open?'✕':'☰'});links.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{links.classList.remove('open');btn.setAttribute('aria-expanded','false');btn.textContent='☰'}));window.addEventListener('resize',()=>{if(window.innerWidth>900){links.classList.remove('open');btn.setAttribute('aria-expanded','false');btn.textContent='☰'}})}
});
