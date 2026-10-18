
(() => {
 const box=document.querySelector("#media-lightbox"), image=document.querySelector("#lightbox-image");
 let previousFocus=null;
 document.querySelectorAll(".full-preview").forEach(a=>a.addEventListener("click",e=>{
   e.preventDefault(); previousFocus=a; image.src=a.dataset.full;
   const link=document.querySelector("#lightbox-page");link.href=a.dataset.page;box.showModal();
 }));
 const close=()=>{if(box.open){box.close();image.removeAttribute("src");previousFocus?.focus();}};
 document.querySelector("#lightbox-close")?.addEventListener("click",close);
 box?.addEventListener("click",e=>{if(e.target===box)close();});
 box?.addEventListener("close",()=>previousFocus?.focus());
 const copy=document.querySelector("#copy-link");
 copy?.addEventListener("click",async()=>{
   const field=document.querySelector("#share-url"),status=document.querySelector("#copy-status");
   try{await navigator.clipboard.writeText(copy.dataset.url);status.textContent="Връзката е копирана.";}
   catch{field.focus();field.select();status.textContent="Копирайте маркираната връзка с Ctrl+C.";}
 });
 // Gallery/lightbox initialization above is independent of this optional fetch.
 const mode=new URLSearchParams(location.search).get("slideshow");
 const src=mode==="missing"?"/media/missing.json":mode==="broken"?"/media/broken.json":window.mediaConfig.slideshowURL;
 let slides=[],idleTimer=null,slideTimer=null,index=0;
 const show=document.querySelector("#slideshow"),slide=document.querySelector("#slide-image");
 const shuffle=a=>{for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}};
 function open(){if(!slides.length||show.open)return;clearTimeout(idleTimer);clearInterval(slideTimer);shuffle(slides);index=Math.floor(Math.random()*slides.length);
   slide.src=slides[index];show.showModal();slideTimer=setInterval(()=>{index=(index+1)%slides.length;slide.src=slides[index];},window.mediaConfig.slideMs);}
 function reset(){clearTimeout(idleTimer);clearInterval(slideTimer);if(show.open)show.close();
   if(slides.length)idleTimer=setTimeout(open,window.mediaConfig.idleMs);}
 ["pointermove","pointerdown","keydown","touchstart","wheel"].forEach(t=>document.addEventListener(t,reset,{passive:true}));
 document.addEventListener("click",e=>{const a=e.target.closest?.('a[href="#slideshow"]');if(!a)return;e.preventDefault();open();});
 fetch(src).then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json();})
 .then(d=>{if(d.schema_version!==1||!Array.isArray(d.images)||d.images.some(x=>typeof x!=="string"||!x.includes("/kolaji/full/")))throw Error("Invalid slideshow");
 slides=[...d.images];document.documentElement.dataset.slideshow="ready";reset();})
 .catch(()=>{document.documentElement.dataset.slideshow="unavailable";});
})();
