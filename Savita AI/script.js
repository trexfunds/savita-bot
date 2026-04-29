const TELEGRAM_BOT_LINK = "https://t.me/thesavitabhabhi_bot";

const header = document.querySelector(".site-header");
const menuToggle = document.querySelector("#menu-toggle");
const mobileMenu = document.querySelector("#mobile-menu");
const hero = document.querySelector(".hero");
const heroBg = document.querySelector(".hero-bg");
const heroModel = document.querySelector(".hero-model");
const heartsLayer = document.querySelector("#hearts-layer");
const revealItems = document.querySelectorAll(".reveal");
const telegramButtons = document.querySelectorAll("[data-telegram]");
const counters = document.querySelectorAll("[data-counter]");
const tiltItems = document.querySelectorAll(".tilt");

telegramButtons.forEach((btn) => {
  btn.setAttribute("href", TELEGRAM_BOT_LINK);
  btn.setAttribute("target", "_blank");
  btn.setAttribute("rel", "noopener noreferrer");
});

document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener("click", (e) => {
    const href = anchor.getAttribute("href");
    if (!href || href === "#") return;
    const target = document.querySelector(href);
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    if (header && header.classList.contains("menu-open")) {
      header.classList.remove("menu-open");
      if (menuToggle) menuToggle.setAttribute("aria-expanded", "false");
    }
  });
});

if (menuToggle && header && mobileMenu) {
  menuToggle.addEventListener("click", () => {
    const willOpen = !header.classList.contains("menu-open");
    header.classList.toggle("menu-open", willOpen);
    menuToggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
  });

  document.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof Node)) return;
    if (!header.classList.contains("menu-open")) return;
    if (menuToggle.contains(target) || mobileMenu.contains(target)) return;
    header.classList.remove("menu-open");
    menuToggle.setAttribute("aria-expanded", "false");
  });
}

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("visible");
      revealObserver.unobserve(entry.target);
    });
  },
  { threshold: 0.16 }
);

revealItems.forEach((item) => revealObserver.observe(item));

let ticking = false;
function onScroll() {
  const y = window.scrollY || 0;
  if (header) {
    header.classList.toggle("shrink", y > 22);
  }
  ticking = false;
}

window.addEventListener("scroll", () => {
  if (ticking) return;
  ticking = true;
  window.requestAnimationFrame(onScroll);
});

if (hero && heroBg) {
  hero.addEventListener("mousemove", (e) => {
    const rect = hero.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    const moveX = px * 10;
    const moveY = py * 8;
    heroBg.style.transform = `scale(1.03) translate(${moveX}px, ${moveY}px)`;

    if (heroModel && window.innerWidth > 640) {
      const rotateY = px * 12;
      const rotateX = py * -8;
      heroModel.style.transform = `translateX(-50%) translateY(0px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    }
  });

  hero.addEventListener("mouseleave", () => {
    heroBg.style.transform = "scale(1.02) translate(0px, 0px)";
    if (heroModel && window.innerWidth > 640) {
      heroModel.style.transform = "translateX(-50%) translateY(0px) rotateX(0deg) rotateY(0deg)";
    }
  });
}

const counterObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = Number(el.getAttribute("data-counter") || "0");
      const duration = 1400;
      const start = performance.now();

      function step(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const value = Math.floor(target * eased);
        el.textContent = formatCounter(target, value);
        if (progress < 1) {
          window.requestAnimationFrame(step);
        }
      }

      window.requestAnimationFrame(step);
      counterObserver.unobserve(el);
    });
  },
  { threshold: 0.4 }
);

function formatCounter(target, value) {
  if (target === 5) return "5.0";
  if (target === 87) return `${value}%`;
  if (target >= 1000000) return `${(value / 1000000).toFixed(1)}M+`;
  if (target >= 100000) return `${Math.floor(value / 1000)}K+`;
  if (target >= 1000) return `${Math.floor(value / 1000)}K+`;
  return `${value}+`;
}

counters.forEach((counter) => counterObserver.observe(counter));

tiltItems.forEach((card) => {
  card.addEventListener("mousemove", (e) => {
    const rect = card.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    card.style.transform = `perspective(900px) rotateX(${py * -5}deg) rotateY(${px * 7}deg)`;
  });

  card.addEventListener("mouseleave", () => {
    card.style.transform = "perspective(900px) rotateX(0deg) rotateY(0deg)";
  });
});

function spawnHeart() {
  if (!heartsLayer) return;
  const heart = document.createElement("span");
  heart.className = "heart-particle";
  heart.textContent = "❤";
  heart.style.left = `${Math.random() * 100}%`;
  heart.style.animationDuration = `${7 + Math.random() * 5}s`;
  heart.style.fontSize = `${8 + Math.random() * 7}px`;
  heartsLayer.appendChild(heart);
  setTimeout(() => heart.remove(), 12500);
}

setInterval(spawnHeart, 850);

onScroll();
