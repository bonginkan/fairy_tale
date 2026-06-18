const tabs = Array.from(document.querySelectorAll(".tab"));
const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));
const copyButton = document.querySelector(".copy-button");

function activateTab(tab) {
  tabs.forEach((item) => {
    const selected = item === tab;
    item.classList.toggle("active", selected);
    item.setAttribute("aria-selected", String(selected));
  });

  panels.forEach((panel) => {
    panel.hidden = panel.id !== tab.getAttribute("aria-controls");
  });
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab));
});

copyButton?.addEventListener("click", async () => {
  const activePanel = panels.find((panel) => !panel.hidden);
  const command = activePanel?.innerText.trim();
  if (!command) return;

  try {
    await navigator.clipboard.writeText(command);
    copyButton.textContent = "Copied";
    setTimeout(() => {
      copyButton.textContent = "Copy command";
    }, 1600);
  } catch {
    copyButton.textContent = "Select and copy";
  }
});
