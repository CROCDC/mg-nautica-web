document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.inline-form input[type="file"]').forEach(function (input) {
    var form = input.closest('form');
    var triggerBtn = form.querySelector('button[type="submit"]');
    if (!triggerBtn) return;

    input.style.display = 'none';
    input.removeAttribute('required');

    triggerBtn.type = 'button';
    triggerBtn.addEventListener('click', function () { input.click(); });

    var wrap = document.createElement('div');
    wrap.className = 'file-preview-wrap';
    triggerBtn.insertAdjacentElement('afterend', wrap);

    var submitBtn = document.createElement('button');
    submitBtn.type = 'submit';
    submitBtn.className = 'btn btn-primary';
    submitBtn.textContent = 'Subir';
    submitBtn.style.display = 'none';
    wrap.insertAdjacentElement('afterend', submitBtn);

    var selectedFiles = [];

    input.addEventListener('change', function () {
      Array.from(input.files).forEach(function (f) {
        var dup = selectedFiles.some(function (sf) {
          return sf.name === f.name && sf.size === f.size;
        });
        if (!dup) selectedFiles.push(f);
      });
      render();
    });

    function syncInput() {
      var dt = new DataTransfer();
      selectedFiles.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
    }

    function render() {
      wrap.innerHTML = '';
      syncInput();

      if (selectedFiles.length === 0) {
        submitBtn.style.display = 'none';
        return;
      }

      selectedFiles.forEach(function (file, index) {
        var url = URL.createObjectURL(file);
        var item = document.createElement('div');
        item.className = 'file-preview-item';

        var media;
        if (file.type.startsWith('image/')) {
          media = document.createElement('img');
          media.src = url;
          media.alt = file.name;
        } else if (file.type.startsWith('video/')) {
          media = document.createElement('video');
          media.src = url;
          media.muted = true;
          media.controls = true;
          media.preload = 'metadata';
        }

        if (media) {
          var label = document.createElement('small');
          label.textContent = file.name;

          var discardBtn = document.createElement('button');
          discardBtn.type = 'button';
          discardBtn.className = 'btn btn-danger btn-sm';
          discardBtn.textContent = '✕';
          discardBtn.title = 'Descartar';
          discardBtn.addEventListener('click', (function (i) {
            return function () {
              URL.revokeObjectURL(url);
              selectedFiles.splice(i, 1);
              render();
            };
          })(index));

          item.appendChild(media);
          item.appendChild(label);
          item.appendChild(discardBtn);
          wrap.appendChild(item);
        }
      });

      submitBtn.style.display = '';
    }
  });
});
