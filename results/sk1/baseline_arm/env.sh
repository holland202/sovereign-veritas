# Source this: contains every write and every git lookup inside /home/user/sk1_base_out
export HOME=/home/user/sk1_base_out/home
export TMPDIR=/home/user/sk1_base_out/tmp
export MPLCONFIGDIR=/home/user/sk1_base_out/mpl
export XDG_CACHE_HOME=/home/user/sk1_base_out/home/.cache
export PYTHONDONTWRITEBYTECODE=1
export GIT_CEILING_DIRECTORIES=/home/user/sk1_base_out/work:/home/user/sk1_base_out/mutants
export GIT_CONFIG_NOSYSTEM=1
# NODEP=1 simulates "dilithium-py not installed" by shadowing the package with one that raises ImportError
if [ "${NODEP:-0}" = "1" ]; then export PYTHONPATH=/home/user/sk1_base_out/block; else unset PYTHONPATH; fi
