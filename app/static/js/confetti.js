const confettiContainer = document.getElementById("confettiLayer");
const icons = ["🧁", "🍰", "🍥", "🥟"];

for (let i = 0; i < 45; i++) {
  let c = document.createElement("span");
  c.innerText = icons[Math.floor(Math.random() * icons.length)];
  c.style.left = Math.random() * 100 + "vw";
  c.style.animationDuration = (5 + Math.random() * 5) + "s";
  c.style.animationDelay = Math.random() * 5 + "s";
  c.style.fontSize = (20 + Math.random() * 14) + "px";
  confettiContainer.appendChild(c);
}
