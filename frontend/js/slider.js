// 轮播图功能
document.addEventListener('DOMContentLoaded', function() {
  const sliderWrapper = document.querySelector('.slider-wrapper');
  const sliderItems = document.querySelectorAll('.slider-item');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const dots = document.querySelectorAll('.dot');

  let currentIndex = 0;
  const totalSlides = sliderItems.length;
  let autoPlayInterval;

  console.log('Slider initialized. Total slides:', totalSlides);

  // 初始化
  function init() {
    if (totalSlides === 0) return;

    console.log('Starting slider initialization...');

    // 绑定事件
    bindEvents();

    // 开始自动播放
    startAutoPlay();
    console.log('Auto-play started');
  }
  
  // 绑定事件
  function bindEvents() {
    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        goToSlide(currentIndex - 1);
        resetAutoPlay();
      });
    }
    
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        goToSlide(currentIndex + 1);
        resetAutoPlay();
      });
    }
    
    dots.forEach((dot, index) => {
      dot.addEventListener('click', () => {
        goToSlide(index);
        resetAutoPlay();
      });
    });
    
    // 键盘控制
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') {
        goToSlide(currentIndex - 1);
        resetAutoPlay();
      } else if (e.key === 'ArrowRight') {
        goToSlide(currentIndex + 1);
        resetAutoPlay();
      }
    });
    
    // 触摸滑动支持
    let touchStartX = 0;
    let touchEndX = 0;
    
    const sliderContainer = document.querySelector('.slider-container');
    
    sliderContainer.addEventListener('touchstart', (e) => {
      touchStartX = e.changedTouches[0].screenX;
      stopAutoPlay();
    }, { passive: true });
    
    sliderContainer.addEventListener('touchend', (e) => {
      touchEndX = e.changedTouches[0].screenX;
      handleSwipe();
      startAutoPlay();
    }, { passive: true });
    
    function handleSwipe() {
      const diff = touchStartX - touchEndX;
      const threshold = 50;
      
      if (Math.abs(diff) > threshold) {
        if (diff > 0) {
          // 向左滑动，显示下一个
          goToSlide(currentIndex + 1);
        } else {
          // 向右滑动，显示上一个
          goToSlide(currentIndex - 1);
        }
      }
    }
    
    // 鼠标悬停时暂停自动播放
    const heroSlider = document.querySelector('.hero-slider');
    heroSlider.addEventListener('mouseenter', stopAutoPlay);
    heroSlider.addEventListener('mouseleave', startAutoPlay);
  }
  
  // 切换到指定幻灯片
  function goToSlide(index) {
    if (index < 0) {
      currentIndex = totalSlides - 1;
    } else if (index >= totalSlides) {
      currentIndex = 0;
    } else {
      currentIndex = index;
    }
    
    updateSlider();
  }
  
  // 更新轮播显示
  function updateSlider() {
    // 使用 transform 移动轮播图
    sliderWrapper.style.transform = `translateX(-${currentIndex * 100}%)`;

    // 触发当前幻灯片的文字动画
    const currentText = sliderItems[currentIndex].querySelector('.slider-text');
    currentText.style.animation = 'none';
    currentText.offsetHeight; // 触发回流
    currentText.style.animation = 'slideUp 0.8s ease-out';

    // 更新圆点状态
    dots.forEach((dot, index) => {
      dot.classList.toggle('active', index === currentIndex);
    });
  }
  
  // 自动播放
  function startAutoPlay() {
    stopAutoPlay();
    console.log('Starting auto-play with 3 second interval');
    autoPlayInterval = setInterval(() => {
      console.log('Auto-playing slide', currentIndex + 1);
      goToSlide(currentIndex + 1);
    }, 3000); // 3秒自动切换
  }
  
  function stopAutoPlay() {
    if (autoPlayInterval) {
      clearInterval(autoPlayInterval);
    }
  }
  
  function resetAutoPlay() {
    stopAutoPlay();
    startAutoPlay();
  }
  
  // 初始化轮播
  init();
});
