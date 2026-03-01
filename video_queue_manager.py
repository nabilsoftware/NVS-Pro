# ==============================================================================
# VIDEO QUEUE MANAGER - Parallel Multi-Video Pipeline
# ==============================================================================
# This module enables processing multiple videos simultaneously using a
# queue-based architecture. Each video progresses through pipeline steps
# independently, maximizing throughput.
#
# Architecture:
#   Video1: [Step1] [Step2] [Step3] [Step4] [Step5] [Step6] [Step7] [Step8]
#   Video2:         [Step1] [Step2] [Step3] [Step4] [Step5] [Step6] [Step7]
#   Video3:                 [Step1] [Step2] [Step3] [Step4] [Step5] [Step6]
#
# Key Features:
#   - Each video gets its own browser profile (no blocking)
#   - Configurable max concurrent videos
#   - Smart resource management (GPU, CPU, memory)
#   - Progress tracking and logging
# ==============================================================================

import os
import sys
import json
import time
import shutil
import logging
import threading
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

# Fix encoding
if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ==============================================================================
# CONFIGURATION
# ==============================================================================

class QueueConfig:
    """Configuration for the video queue manager"""

    # Maximum concurrent videos at different pipeline stages
    MAX_CONCURRENT_VIDEOS = 3  # How many videos can process simultaneously

    # Stage-specific concurrency limits (some steps are resource-heavy)
    MAX_CONCURRENT_STEP1 = 2   # Smart Interview Processing (CPU/GPU heavy)
    MAX_CONCURRENT_STEP2 = 3   # Styling (GPU heavy)
    MAX_CONCURRENT_STEP3 = 3   # Voiceover (Browser-based, each gets own window)
    MAX_CONCURRENT_STEP4 = 3   # B-roll rearrangement (CPU)
    MAX_CONCURRENT_STEP5 = 2   # Video assembly (GPU heavy)
    MAX_CONCURRENT_STEP6 = 3   # Ranking (CPU light)
    MAX_CONCURRENT_STEP7 = 2   # Combine (GPU heavy)
    MAX_CONCURRENT_STEP8 = 2   # YouTube upload (Network)

    # Browser profile settings
    BROWSER_PROFILE_BASE = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / 'NabilVideoStudioPro'
    MASTER_BROWSER_PROFILE = BROWSER_PROFILE_BASE / 'browser_profile'

    # Timing
    QUEUE_CHECK_INTERVAL = 2  # Seconds between queue checks
    STEP_COMPLETION_WAIT = 1  # Seconds to wait after step completion


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

class VideoStatus(Enum):
    """Status of a video in the queue"""
    QUEUED = "queued"
    PROCESSING = "processing"
    WAITING = "waiting"  # Waiting for resource (e.g., browser profile)
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class StepStatus(Enum):
    """Status of a pipeline step"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VideoTask:
    """Represents a video being processed in the queue"""
    video_id: str
    video_name: str
    input_folder: Path
    output_folder: Path
    broll_folder: Path
    profile_info: Dict

    # Status tracking
    status: VideoStatus = VideoStatus.QUEUED
    current_step: int = 0
    step_statuses: Dict[int, StepStatus] = field(default_factory=dict)

    # Browser profile for this video (unique per video)
    browser_profile_path: Optional[Path] = None

    # Timing
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    step_times: Dict[int, float] = field(default_factory=dict)

    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2

    def __post_init__(self):
        # Initialize step statuses
        for step in range(9):  # Steps 0-8
            self.step_statuses[step] = StepStatus.PENDING


@dataclass
class StepSemaphore:
    """Semaphore for controlling concurrent access to pipeline steps"""
    step_num: int
    max_concurrent: int
    current_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self) -> bool:
        """Try to acquire a slot for this step"""
        with self.lock:
            if self.current_count < self.max_concurrent:
                self.current_count += 1
                return True
            return False

    def release(self):
        """Release a slot for this step"""
        with self.lock:
            if self.current_count > 0:
                self.current_count -= 1


# ==============================================================================
# BROWSER PROFILE MANAGER
# ==============================================================================

class BrowserProfileManager:
    """
    Manages browser profiles for parallel voiceover generation.
    Each video gets its own browser profile to avoid conflicts.
    """

    def __init__(self, base_path: Path, master_profile: Path):
        self.base_path = base_path
        self.master_profile = master_profile
        self.active_profiles: Dict[str, Path] = {}
        self.lock = threading.Lock()

        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_profile_for_video(self, video_id: str) -> Path:
        """
        Get or create a browser profile for a video.
        Copies cookies from master profile to enable Fish Audio login.
        """
        with self.lock:
            if video_id in self.active_profiles:
                return self.active_profiles[video_id]

            # Create unique profile path
            profile_path = self.base_path / f'browser_profile_{video_id}'

            # If profile doesn't exist, copy from master
            if not profile_path.exists():
                self._create_profile_from_master(profile_path)

            self.active_profiles[video_id] = profile_path
            return profile_path

    def _create_profile_from_master(self, profile_path: Path):
        """Create a new profile by copying essential files from master"""
        profile_path.mkdir(parents=True, exist_ok=True)

        if not self.master_profile.exists():
            logging.warning(f"Master profile not found: {self.master_profile}")
            return

        # Copy only essential cookie/session files (not the whole profile)
        essential_files = [
            'Cookies',
            'Cookies-journal',
            'Local State',
            'Preferences',
        ]

        essential_dirs = [
            'Default',  # Contains cookies and login state
        ]

        # Copy essential files
        for file_name in essential_files:
            src = self.master_profile / file_name
            if src.exists():
                try:
                    shutil.copy2(src, profile_path / file_name)
                except Exception as e:
                    logging.warning(f"Could not copy {file_name}: {e}")

        # Copy Default directory (contains session data)
        for dir_name in essential_dirs:
            src_dir = self.master_profile / dir_name
            if src_dir.exists():
                dst_dir = profile_path / dir_name
                try:
                    if dst_dir.exists():
                        shutil.rmtree(dst_dir)
                    shutil.copytree(src_dir, dst_dir,
                                   ignore=shutil.ignore_patterns('Cache', 'Code Cache',
                                                                  'GPUCache', 'Service Worker'))
                except Exception as e:
                    logging.warning(f"Could not copy {dir_name}: {e}")

        logging.info(f"Created browser profile: {profile_path}")

    def cleanup_browser_locks(self, profile_path: Path):
        """Remove lock files that may block browser launch"""
        lock_files = ['SingletonLock', 'SingletonCookie', 'SingletonSocket', 'lockfile']
        for lock_file in lock_files:
            lock_path = profile_path / lock_file
            try:
                if lock_path.exists():
                    os.remove(lock_path)
            except Exception:
                pass

    def release_profile(self, video_id: str, cleanup: bool = False):
        """Release a browser profile after video processing completes"""
        with self.lock:
            if video_id in self.active_profiles:
                profile_path = self.active_profiles[video_id]

                # Clean up lock files
                self.cleanup_browser_locks(profile_path)

                # Optionally delete the profile to save space
                if cleanup:
                    try:
                        shutil.rmtree(profile_path)
                        logging.info(f"Cleaned up browser profile: {profile_path}")
                    except Exception as e:
                        logging.warning(f"Could not cleanup profile: {e}")

                del self.active_profiles[video_id]

    def get_active_count(self) -> int:
        """Get number of active browser profiles"""
        with self.lock:
            return len(self.active_profiles)


# ==============================================================================
# VIDEO QUEUE MANAGER
# ==============================================================================

class VideoQueueManager:
    """
    Main queue manager for parallel video processing.
    Coordinates multiple videos through the pipeline simultaneously.
    """

    def __init__(self, config: QueueConfig = None):
        self.config = config or QueueConfig()

        # Queue and task tracking
        self.video_queue: List[VideoTask] = []
        self.active_tasks: Dict[str, VideoTask] = {}
        self.completed_tasks: List[VideoTask] = []
        self.failed_tasks: List[VideoTask] = []

        # Threading
        self.queue_lock = threading.Lock()
        self.is_running = False
        self.executor: Optional[ThreadPoolExecutor] = None

        # Step semaphores for resource control
        self.step_semaphores = {
            0: StepSemaphore(0, self.config.MAX_CONCURRENT_VIDEOS),
            1: StepSemaphore(1, self.config.MAX_CONCURRENT_STEP1),
            2: StepSemaphore(2, self.config.MAX_CONCURRENT_STEP2),
            3: StepSemaphore(3, self.config.MAX_CONCURRENT_STEP3),
            4: StepSemaphore(4, self.config.MAX_CONCURRENT_STEP4),
            5: StepSemaphore(5, self.config.MAX_CONCURRENT_STEP5),
            6: StepSemaphore(6, self.config.MAX_CONCURRENT_STEP6),
            7: StepSemaphore(7, self.config.MAX_CONCURRENT_STEP7),
            8: StepSemaphore(8, self.config.MAX_CONCURRENT_STEP8),
        }

        # Browser profile manager
        self.browser_manager = BrowserProfileManager(
            self.config.BROWSER_PROFILE_BASE,
            self.config.MASTER_BROWSER_PROFILE
        )

        # Callbacks for step execution (set by content_creator.py)
        self.step_callbacks: Dict[int, Callable] = {}

        # Logging
        self.logger = logging.getLogger('VideoQueueManager')

    def add_video(self, video_task: VideoTask) -> str:
        """Add a video to the processing queue"""
        with self.queue_lock:
            # Assign unique browser profile
            video_task.browser_profile_path = self.browser_manager.get_profile_for_video(
                video_task.video_id
            )

            self.video_queue.append(video_task)
            self.logger.info(f"Added video to queue: {video_task.video_name} (ID: {video_task.video_id})")
            self.logger.info(f"  Browser profile: {video_task.browser_profile_path}")

            return video_task.video_id

    def add_videos_batch(self, video_tasks: List[VideoTask]) -> List[str]:
        """Add multiple videos to the queue"""
        video_ids = []
        for task in video_tasks:
            video_id = self.add_video(task)
            video_ids.append(video_id)

        self.logger.info(f"Added {len(video_ids)} videos to queue")
        return video_ids

    def register_step_callback(self, step_num: int, callback: Callable):
        """
        Register a callback function for a pipeline step.
        The callback should accept (video_task, step_num) and return bool (success/fail)
        """
        self.step_callbacks[step_num] = callback
        self.logger.info(f"Registered callback for Step {step_num}")

    def start(self):
        """Start the queue processing"""
        if self.is_running:
            self.logger.warning("Queue manager is already running")
            return

        self.is_running = True
        self.executor = ThreadPoolExecutor(max_workers=self.config.MAX_CONCURRENT_VIDEOS)

        # Start the main queue processing loop in a thread
        self.process_thread = threading.Thread(target=self._process_queue_loop, daemon=True)
        self.process_thread.start()

        self.logger.info(f"Queue manager started (max concurrent: {self.config.MAX_CONCURRENT_VIDEOS})")

    def stop(self, wait_for_completion: bool = True):
        """Stop the queue processing"""
        self.is_running = False

        if wait_for_completion and self.executor:
            self.executor.shutdown(wait=True)
        elif self.executor:
            self.executor.shutdown(wait=False)

        self.logger.info("Queue manager stopped")

    def _process_queue_loop(self):
        """Main loop that processes the video queue"""
        while self.is_running:
            try:
                self._process_queue_tick()
            except Exception as e:
                self.logger.error(f"Error in queue processing: {e}")

            time.sleep(self.config.QUEUE_CHECK_INTERVAL)

    def _process_queue_tick(self):
        """Single tick of queue processing"""
        with self.queue_lock:
            # Get videos that can start processing
            available_slots = self.config.MAX_CONCURRENT_VIDEOS - len(self.active_tasks)

            if available_slots <= 0:
                return

            # Find queued videos ready to start
            videos_to_start = []
            for video in self.video_queue:
                if video.status == VideoStatus.QUEUED and len(videos_to_start) < available_slots:
                    videos_to_start.append(video)

            # Start processing each video
            for video in videos_to_start:
                self.video_queue.remove(video)
                video.status = VideoStatus.PROCESSING
                video.start_time = time.time()
                self.active_tasks[video.video_id] = video

                # Submit to executor
                self.executor.submit(self._process_video, video)
                self.logger.info(f"Started processing: {video.video_name}")

    def _process_video(self, video: VideoTask):
        """Process a single video through all pipeline steps"""
        try:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"PROCESSING: {video.video_name}")
            self.logger.info(f"{'='*60}")

            # Process each step
            for step_num in range(9):  # Steps 0-8
                if not self.is_running:
                    video.status = VideoStatus.PAUSED
                    return

                # Wait for step semaphore
                semaphore = self.step_semaphores[step_num]
                while not semaphore.acquire():
                    if not self.is_running:
                        return
                    time.sleep(0.5)

                try:
                    success = self._execute_step(video, step_num)

                    if success:
                        video.step_statuses[step_num] = StepStatus.COMPLETED
                        video.current_step = step_num + 1
                        self.logger.info(f"[{video.video_name}] Step {step_num} COMPLETED")
                    else:
                        video.step_statuses[step_num] = StepStatus.FAILED
                        raise Exception(f"Step {step_num} failed")

                finally:
                    semaphore.release()

                time.sleep(self.config.STEP_COMPLETION_WAIT)

            # All steps completed
            video.status = VideoStatus.COMPLETED
            video.end_time = time.time()

            self._on_video_completed(video)

        except Exception as e:
            self.logger.error(f"[{video.video_name}] Processing failed: {e}")
            video.status = VideoStatus.FAILED
            video.error_message = str(e)
            video.end_time = time.time()

            self._on_video_failed(video)

    def _execute_step(self, video: VideoTask, step_num: int) -> bool:
        """Execute a single pipeline step for a video"""
        step_start = time.time()

        self.logger.info(f"[{video.video_name}] Starting Step {step_num}...")
        video.step_statuses[step_num] = StepStatus.RUNNING

        # Check if callback is registered
        if step_num not in self.step_callbacks:
            self.logger.warning(f"No callback registered for Step {step_num}")
            return True  # Skip step if no callback

        try:
            # Execute the step callback
            callback = self.step_callbacks[step_num]
            success = callback(video, step_num)

            # Record timing
            video.step_times[step_num] = time.time() - step_start

            return success

        except Exception as e:
            self.logger.error(f"[{video.video_name}] Step {step_num} error: {e}")
            return False

    def _on_video_completed(self, video: VideoTask):
        """Handle video completion"""
        with self.queue_lock:
            if video.video_id in self.active_tasks:
                del self.active_tasks[video.video_id]
            self.completed_tasks.append(video)

        # Release browser profile
        self.browser_manager.release_profile(video.video_id, cleanup=True)

        # Calculate processing time
        total_time = video.end_time - video.start_time

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"COMPLETED: {video.video_name}")
        self.logger.info(f"Total time: {total_time/60:.1f} minutes")
        self.logger.info(f"{'='*60}\n")

    def _on_video_failed(self, video: VideoTask):
        """Handle video failure"""
        with self.queue_lock:
            if video.video_id in self.active_tasks:
                del self.active_tasks[video.video_id]

            # Check if retry is possible
            if video.retry_count < video.max_retries:
                video.retry_count += 1
                video.status = VideoStatus.QUEUED
                video.current_step = 0  # Start from beginning
                self.video_queue.append(video)
                self.logger.info(f"Retrying video: {video.video_name} (attempt {video.retry_count})")
            else:
                self.failed_tasks.append(video)
                self.browser_manager.release_profile(video.video_id, cleanup=True)
                self.logger.error(f"Video failed permanently: {video.video_name}")

    def get_status(self) -> Dict:
        """Get current queue status"""
        with self.queue_lock:
            return {
                'queued': len(self.video_queue),
                'active': len(self.active_tasks),
                'completed': len(self.completed_tasks),
                'failed': len(self.failed_tasks),
                'active_browsers': self.browser_manager.get_active_count(),
                'is_running': self.is_running,
                'active_videos': [
                    {
                        'name': v.video_name,
                        'current_step': v.current_step,
                        'status': v.status.value
                    }
                    for v in self.active_tasks.values()
                ]
            }

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all videos to complete processing"""
        start_time = time.time()

        while True:
            with self.queue_lock:
                if not self.video_queue and not self.active_tasks:
                    return True

            if timeout and (time.time() - start_time) > timeout:
                return False

            time.sleep(1)

    def print_status(self):
        """Print current queue status to console"""
        status = self.get_status()

        print(f"\n{'='*60}")
        print(f"VIDEO QUEUE STATUS")
        print(f"{'='*60}")
        print(f"Queued:    {status['queued']}")
        print(f"Active:    {status['active']}")
        print(f"Completed: {status['completed']}")
        print(f"Failed:    {status['failed']}")
        print(f"Browsers:  {status['active_browsers']}")
        print(f"{'='*60}")

        if status['active_videos']:
            print("Active Videos:")
            for v in status['active_videos']:
                print(f"  - {v['name']}: Step {v['current_step']} ({v['status']})")

        print(f"{'='*60}\n")


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def create_video_task(
    video_name: str,
    input_folder: Path,
    output_folder: Path,
    broll_folder: Path,
    profile_info: Dict
) -> VideoTask:
    """Helper to create a VideoTask with auto-generated ID"""
    import uuid

    video_id = f"{video_name}_{uuid.uuid4().hex[:8]}"

    return VideoTask(
        video_id=video_id,
        video_name=video_name,
        input_folder=input_folder,
        output_folder=output_folder,
        broll_folder=broll_folder,
        profile_info=profile_info
    )


# ==============================================================================
# STANDALONE TESTING
# ==============================================================================

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Video Queue Manager - Test Mode")
    print("="*60)

    # Create manager
    manager = VideoQueueManager()

    # Register dummy callbacks for testing
    for step in range(9):
        def dummy_callback(video, step_num, s=step):
            print(f"  [TEST] Executing Step {s} for {video.video_name}")
            time.sleep(1)  # Simulate work
            return True
        manager.register_step_callback(step, dummy_callback)

    # Add test videos
    for i in range(5):
        task = create_video_task(
            video_name=f"TestVideo_{i+1}",
            input_folder=Path(f"./input/video_{i+1}"),
            output_folder=Path(f"./output/video_{i+1}"),
            broll_folder=Path("./broll"),
            profile_info={'name': 'TestProfile', 'suffix': 'TEST'}
        )
        manager.add_video(task)

    # Start processing
    manager.start()

    # Monitor progress
    try:
        while not manager.wait_for_completion(timeout=1):
            manager.print_status()
    except KeyboardInterrupt:
        print("\nStopping...")
        manager.stop()

    # Final status
    manager.print_status()
    print("Test complete!")
