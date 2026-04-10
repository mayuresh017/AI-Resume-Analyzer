const resumeInput = document.getElementById('resume');
const fileName = document.getElementById('fileName');
const resumeForm = document.getElementById('resumeForm');
const analyzeButton = document.getElementById('analyzeButton');

if (resumeInput && fileName) {
  resumeInput.addEventListener('change', () => {
    fileName.textContent = resumeInput.files.length
      ? `Selected file: ${resumeInput.files[0].name}`
      : 'Accepted formats: PDF, DOCX, TXT';
  });
}

if (resumeForm && analyzeButton) {
  resumeForm.addEventListener('submit', () => {
    analyzeButton.disabled = true;
    analyzeButton.textContent = 'Analyzing...';
  });
}

document.addEventListener('DOMContentLoaded', function () {
  const toggleBtn = document.getElementById('theme-toggle');

  if (!toggleBtn) return;

  const savedTheme = localStorage.getItem('theme');

  if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
    toggleBtn.textContent = '☀️ Light Mode';
  } else {
    toggleBtn.textContent = '🌙 Dark Mode';
  }

  toggleBtn.addEventListener('click', function () {
    document.body.classList.toggle('dark-mode');

    if (document.body.classList.contains('dark-mode')) {
      localStorage.setItem('theme', 'dark');
      toggleBtn.textContent = '☀️ Light Mode';
    } else {
      localStorage.setItem('theme', 'light');
      toggleBtn.textContent = '🌙 Dark Mode';
    }
  });
});