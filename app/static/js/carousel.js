const slides = [
  "/static/images/slide1.jpg",
  "/static/images/slide2.jpg",
  "/static/images/slide3.jpg",
  "/static/images/slide4.jpg"
];

let idx = 0;
const img = document.getElementById("slideImage");

function showSlide(n) {
  idx = (n + slides.length) % slides.length;
  img.style.opacity = 0;
  setTimeout(() => {
    img.src = slides[idx];
    img.style.opacity = 1;
  }, 200);
}

document.getElementById("prevBtn").onclick = () => showSlide(idx - 1);
document.getElementById("nextBtn").onclick = () => showSlide(idx + 1);
