document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('input[type="file"]').forEach(function (input) {
    var wrap = document.createElement('div');
    wrap.className = 'file-preview-wrap';
    input.insertAdjacentElement('afterend', wrap);

    input.addEventListener('change', function () {
      wrap.innerHTML = '';
      Array.from(input.files).forEach(function (file) {
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
          item.appendChild(media);
          item.appendChild(label);
          wrap.appendChild(item);
        }
      });
    });
  });
});
