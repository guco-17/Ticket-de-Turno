document.addEventListener('DOMContentLoaded', () => {
    const captchaImage = document.querySelector('#captcha-image');
    const refreshButton = document.querySelector('#refresh-captcha');

    refreshButton.addEventListener('click', () => {
        const captchaUrl = new URL(captchaImage.src);
        captchaUrl.searchParams.set('refresh', Date.now());
        captchaImage.src = captchaUrl.toString();
    });
});
