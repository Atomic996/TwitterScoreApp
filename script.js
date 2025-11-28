document.addEventListener('DOMContentLoaded', () => {
    const calculateButton = document.getElementById('calculateButton');
    const usernameInput = document.getElementById('usernameInput');
    const resultContainer = document.getElementById('resultContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const downloadImageButton = document.getElementById('downloadImage');

    calculateButton.addEventListener('click', async () => {
        const username = usernameInput.value.trim().replace('@', ''); // إزالة الـ @ إذا أدخلها المستخدم
        
        // إعادة تهيئة الحالة
        resultContainer.classList.add('hidden');
        errorMessage.textContent = '';
        downloadImageButton.classList.add('hidden');

        if (!username) {
            errorMessage.textContent = 'الرجاء إدخال اسم المستخدم.';
            return;
        }

        loadingIndicator.classList.remove('hidden');

        try {
            // الخطوة 1: استدعاء API لحساب السكور
            const scoreResponse = await fetch(`/api/score/${username}`);
            const data = await scoreResponse.json();

            loadingIndicator.classList.add('hidden');

            if (scoreResponse.ok) {
                // عرض البيانات الإحصائية
                document.getElementById('usernameDisplay').textContent = `@${username}`;
                document.getElementById('scoreDisplay').textContent = data.score;
                document.getElementById('followersCount').textContent = data.followers.toLocaleString('ar-EG');
                document.getElementById('mentionsCount').textContent = data.mentions_count.toLocaleString('ar-EG');
                document.getElementById('profileImage').src = data.profile_image_url.replace('_normal', '_400x400');
                
                resultContainer.classList.remove('hidden');
                
                // الخطوة 2: جلب الصورة المولدة بعد ظهور النتيجة
                const imageResponse = await fetch(`/api/score/image/${username}/${data.score}`);
                if (imageResponse.ok) {
                    // تحويل الصورة إلى Blob ومن ثم إلى رابط يمكن تحميله
                    const imageBlob = await imageResponse.blob();
                    const imageUrl = URL.createObjectURL(imageBlob);
                    
                    downloadImageButton.href = imageUrl;
                    downloadImageButton.classList.remove('hidden');
                }
                

            } else {
                // معالجة الأخطاء من الخادم
                errorMessage.textContent = `خطأ: ${data.error || 'فشل في استرجاع البيانات'}`;
            }

        } catch (error) {
            loadingIndicator.classList.add('hidden');
            errorMessage.textContent = 'حدث خطأ غير متوقع. تأكد من أن الخادم يعمل.';
            console.error('Fetch error:', error);
        }
    });
});
