// @source: https://github.com/tejo-esperanto/pasportaservo/blob/master/hosting/static/js/file-input-widget.js
// @license magnet:?xt=urn:btih:0b31508aeb0634b347b8270c7bee4d411b5d4109&dn=agpl-3.0.txt AGPL v3


$(function() {

    const IS_FILE_DRAGANDDROP_AVAILABLE = (function() {
        let div = document.createElement('div');
        return (
            (('draggable' in div) || ('ondragstart' in div && 'ondrop' in div))
            && ('FormData' in window) && ('FileReader' in window)
        );
    })();

    Array.prototype.forEach.call(
        document.querySelectorAll('[type="file"][data-advanced]'),
        function (fileInputElem) {
            fileInputElem.addEventListener('change', handleFiles);
            try {
                new DataTransfer();
                fileInputElem.dataset.supportsManualRevert = '';
            }
            catch (e) {}

            let fileButtonElem = document.querySelector(`label[for="${fileInputElem.id}"].btn`);
            fileInputElem.addEventListener('focus', () => fileButtonElem.classList.add('focus'));
            fileInputElem.addEventListener('blur', () => fileButtonElem.classList.remove('focus'));

            let dropzone = document.getElementById(`${fileInputElem.id}_dropzone`);

            if (IS_FILE_DRAGANDDROP_AVAILABLE) {
                let control = dropzone.querySelector('[id$="_dragdrop_control"]');
                control.querySelector('.fa').classList.add(...control.dataset.icon.split(' '));
                delete control.dataset.icon;
                control.append(control.dataset.content);
                delete control.dataset.content;
                control.classList.add('active');

                dropzone.addEventListener('dragover', dropIndicate.bind(dropzone, true));
                dropzone.addEventListener('dragleave', dropIndicate.bind(dropzone, false));
                dropzone.addEventListener('drop', handleFiles);
            }
            // TODO Comments
            dropzone.querySelector('.image-input-placeholder')
                    .addEventListener('click', () => fileButtonElem.click());
            // TODO Comments
            dropzone.querySelector('.file-input-reset .close')
                    .addEventListener('click', resetFileSelection);
            let resetButtonTextElement = dropzone.querySelector('.file-input-reset .close .tx');
            resetButtonTextElement.textContent = resetButtonTextElement.dataset.initialContent;
        }
    );

    function dropPrep(event) {
        event.stopPropagation();
        event.preventDefault();
    }
    function dropIndicate(canDrop, event) {
        dropPrep(event);
        this.classList.toggle('dragover', canDrop);
    }

    function revertInputFieldValue(fileInputElem, event, forceClear = false) {
        if (event.type == 'change') {
            let stashedFiles = $(fileInputElem).data('file-to-upload');
            if ('supportsManualRevert' in fileInputElem.dataset && stashedFiles) {
                // In some browsers, clicking "Cancel" in the file selection dialog clears the
                // value of the File input field.
                // For these cases, and when the newly selected file is not accepted (not an
                // image; overly large file), we manually restore the previously selected file.
                fileInputElem.files = stashedFiles;
            } else if (forceClear) {
                console.log(`\t Clearing fileInput`);
                fileInputElem.value = null;
            }
        }
    }

    function revertFileSelectionFallback(dropzone) {
        let resetControlElement = dropzone.querySelector('.file-input-reset'),
            resetButtonElement = resetControlElement.querySelector('.close');
        if (resetControlElement.classList.contains('revert')) {
            resetControlElement.classList.add('can-revert');
            resetControlElement.classList.remove('revert');
        }
        resetButtonElement.click();
    }

    function handleFiles(event) {
        let fileInputElem, dropzone;
        let files;
        if (event.type == 'drop') {
            dropPrep(event);
            console.log(`FILE EVENT ${event.type}`);
            console.log(event.dataTransfer);
            dropzone = this;
            fileInputElem = document.getElementById(
                dropzone.id.substring(0, dropzone.id.length - '_dropzone'.length));
            console.log(fileInputElem);
            dropzone.classList.remove('dragover');
            files = event.dataTransfer.files;
        }
        else {
            fileInputElem = this;
            dropzone = document.getElementById(fileInputElem.id + '_dropzone');
            console.log(`FILE EVENT ${event.type}`);
            console.log(fileInputElem);
            console.log(dropzone);
            files = fileInputElem.files;
        }
        if (!files.length) {
            console.log(`No files selected via "${event.type}"!`);
            revertInputFieldValue(fileInputElem, event);
            return;
        }

        let imageFile;
        for (let i = 0; i < files.length; i++) {
            imageFile = files[i];
            console.log(`#${i+1}. ${imageFile.type} ${imageFile.size} bytes (${imageFile.name})`);
            if (imageFile.type.startsWith('image/')) {
                break;
            }
            else {
                imageFile = null;
            }
        }

        let fileErrorText = "", warningId = `error_file_${fileInputElem.id}`;
        // TODO: .trimmed = overflow-x: hidden; text-overflow: ellipsis;
        // Need to trim only the filename, not the whole help block.
        if (!imageFile) {
            if (files.length == 1 && files[0].name.trim()) {
                fileErrorText = gettext("\u201C\u2009[FILENAME]\u2009\u201D: Please choose an image.");
                fileErrorText = fileErrorText.replace("[FILENAME]", files[0].name.trim());
            }
            else {
                fileErrorText = gettext("Please choose an image.");
            }
        }
        else if (fileInputElem.dataset.supportsManualRevert === undefined && files.length > 1) {
            fileErrorText = gettext("Please choose a single image.");
        }
        else if (imageFile.size > fileInputElem.maxLength) {
            if (imageFile.name.trim()) {
                fileErrorText = gettext("\u201C\u2009[FILENAME]\u2009\u201D: Image is too heavy.");
                fileErrorText = fileErrorText.replace("[FILENAME]", imageFile.name.trim());
            }
            else {
                fileErrorText = gettext("Image is too heavy.");
            }
        }
        if (fileErrorText) {
            console.log(`E [${fileErrorText}]`);
            console.log("reverting file input");
            revertInputFieldValue(fileInputElem, event, true);
            if (fileInputElem.dataset.supportsManualRevert === undefined) {
                revertFileSelectionFallback(dropzone);
            }
            console.log("displaying the error");
            showFieldError(dropzone, warningId, fileErrorText, {html: true, manualHandling: true});
            return;
        }

        new PreviewImageLoader(dropzone, imageFile, warningId, event).start();
    }

    class PreviewImageLoader {
        constructor(containerElement, imageFile, warningId, originalEvent) {
            this.containerElement = containerElement;
            this.fileInputElement = document.getElementById(containerElement.dataset.fileInput);
            this.previewElement = containerElement.querySelector('.image-input-preview');
            this.imageFile = imageFile;
            this.warningId = warningId;
            this.originalEvent = originalEvent;
            this.originalFiles = originalEvent.dataTransfer && originalEvent.dataTransfer.files
                                 || this.fileInputElement.files;
            this.originalItems = originalEvent.dataTransfer && originalEvent.dataTransfer.items;
        }

        successCallback() {
            this.previewElement.alt = this.imageFile.name;
            URL.revokeObjectURL(this.previewElement.src);
            let $container = $(this.containerElement),
                $resetControl = $container.find('.file-input-reset');
            $container.find('.image-input-initial, .image-input-placeholder').hide();
            $(this.previewElement).show();
            updateResetControl(
                $resetControl[0],
                $container.hasClass('has-initial')
                && !($resetControl.hasClass('revert') || $resetControl.hasClass('can-revert')));
            if ($resetControl.hasClass('revert')) {
                $resetControl.addClass('can-revert').removeClass('revert');
            }
            $resetControl.show();

            this.previewElement.removeEventListener(
                'error', this.handlers.get(this).error, {passive: true, once: true}
            );

            if ('supportsManualRevert' in this.fileInputElement.dataset) {
                let dtContainer = new DataTransfer();
                dtContainer.items.add(this.imageFile);
                if (this.originalEvent.type == 'drop') {
                    console.log("SUCCESS CALLBACK AFTER DROP (*1), files:");
                    console.log(dtContainer.files);
                    this.fileInputElement.files = dtContainer.files;
                }
                $(this.fileInputElement).data('file-to-upload', dtContainer.files);
            }
            else {
                if (this.originalEvent.type == 'drop') {
                    console.log("SUCCESS CALLBACK AFTER DROP (*2), files:");
                    console.log(this.originalFiles);
                    this.fileInputElement.files = this.originalEvent.dataTransfer.files;
                }
            }
            clearFieldError(this.containerElement, this.warningId);

            let $resetButton = $resetControl.find('.close');
            let clearCheckbox = document.getElementById($resetButton.data('checkbox'));
            if (clearCheckbox) {
                clearCheckbox.checked = false;
            }
        }

        errorCallback() {
            this.previewElement.removeEventListener(
                'load', this.handlers.get(this).success, {passive: true, once: true}
            );

            let fileErrorText;
            if (this.imageFile.name.trim()) {
                fileErrorText = gettext("\u201C\u2009[FILENAME]\u2009\u201D: Corrupted image.");
                fileErrorText = fileErrorText.replace("[FILENAME]", this.imageFile.name.trim());
            }
            else {
                fileErrorText = gettext("Corrupted image.");
            }
            // TODO: Also revert the img.src...
            revertInputFieldValue(this.fileInputElement, this.originalEvent, true);
            if (this.fileInputElement.dataset.supportsManualRevert === undefined) {
                revertFileSelectionFallback(this.containerElement);
            }
            showFieldError(
                this.containerElement, this.warningId, fileErrorText,
                {html: true, manualHandling: true}
            );
        }

        start() {
            this.handlers = new WeakMap();
            this.handlers.set(
                this,
                {
                    success: this.successCallback.bind(this),
                    error: this.errorCallback.bind(this),
                }
            );
            this.previewElement.addEventListener(
                'load', this.handlers.get(this).success, {passive: true, once: true}
            );
            this.previewElement.addEventListener(
                'error', this.handlers.get(this).error, {passive: true, once: true}
            );
            this.previewElement.src = URL.createObjectURL(this.imageFile);
        }
    }

    function updateResetControl(controlElement, fileUpdated = false) {
        let button = controlElement.querySelector('.close'),
            icon = button.querySelector('.fa'),
            text = button.querySelector('.tx');
        if (fileUpdated) {
            icon.classList.add(icon.dataset.updatedIcon);
            icon.classList.remove(icon.dataset.initialIcon);
            text.textContent = text.dataset.updatedContent;
            button.setAttribute('title', button.dataset.updatedTitle);
        }
        else {
            icon.classList.add(icon.dataset.initialIcon);
            icon.classList.remove(icon.dataset.updatedIcon);
            text.textContent = text.dataset.initialContent;
            button.setAttribute('title', button.dataset.initialTitle);
        }
    }

    function resetFileSelection(event) {
        let dropzone = this.closest('[id$="_dropzone"]'),
            resetControlElement = this.closest('.file-input-reset'),
            fileInputElement = document.getElementById(dropzone.dataset.fileInput);

        let $currentValueElement = $(dropzone.querySelector('.image-input-preview')),
            currentValueWasVisible = $currentValueElement.is(':visible');
        $currentValueElement.hide();
        $currentValueElement.removeAttr('src alt');

        let $initialValueElement = $(dropzone.querySelector('.image-input-initial')),
            initialValueWasVisible = $initialValueElement.is(':visible');
        let $placeholderElement = $(dropzone.querySelector('.image-input-placeholder'));
        if ($initialValueElement.length > 0 && currentValueWasVisible
                && !resetControlElement.classList.contains('can-revert')) {
            $initialValueElement.show();
            fileInputElement.value = null;
            updateResetControl(resetControlElement);
        }
        else if ($initialValueElement.length > 0
                    && resetControlElement.classList.contains('revert')) {
            $initialValueElement.show();
            $placeholderElement.hide();
            let clearCheckbox = document.getElementById(this.dataset.checkbox);
            if (clearCheckbox) {
                clearCheckbox.checked = false;
            }
            updateResetControl(resetControlElement);
            resetControlElement.classList.remove('revert');
        }
        else {
            $initialValueElement.hide();
            $placeholderElement.show();
            fileInputElement.value = null;
            // TODO Comments
            if (initialValueWasVisible || resetControlElement.classList.contains('can-revert')) {
                let clearCheckbox = document.getElementById(this.dataset.checkbox);
                if (clearCheckbox) {
                    clearCheckbox.checked = true;
                }
                updateResetControl(resetControlElement, true);
                resetControlElement.classList.add('revert');
                resetControlElement.classList.remove('can-revert');
            }
            else {
                $(resetControlElement).hide();
            }
        }
        $(fileInputElement).removeData('file-to-upload');
        clearFieldError(dropzone, `error_file_${dropzone.dataset.fileInput}`);
    }

});


// @license-end
