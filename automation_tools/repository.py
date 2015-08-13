"""Taks for managing repositories"""
from __future__ import print_function

import sys

from automation_tools.utils import distro_info
from fabric.api import hide, put, run
from functools import wraps

if sys.version_info[0] == 2:
    from StringIO import StringIO  # pylint:disable=import-error
else:
    from io import StringIO


def _silencer(func):
    """Decorator which runs the wrapped function with hide('stdout') if the
    ``silent`` keyword argument is provided.

    The ``silent`` keyword argument will be removed from the kwargs before
    calling the wrapped function.

    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        silent = kwargs.pop('silent', False)
        if silent:
            with hide('stdout'):
                return func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


@_silencer
def disable_repos(*args, **kwargs):
    """Disable repos passed as ``args`` using ``subscription-manager repos
    --disable``.

    For example::

        disable_repos('repo1', 'repo2')

    Will run the command ``subscription-manager repos --disable "repo1"
    --disable "repo2"``.

    If the keyword argument ``silent`` is ``True`` then the stdout output will
    be hidden.

    """
    run('subscription-manager repos {0}'
        .format(' '.join(['--disable "{0}"'.format(repo) for repo in args])))


def delete_custom_repos(**args):
    """Delete repos files on ``/etc/yum.repos.d``.

    All files that match ``<filename>.repo`` will be deleted. Be aware that
    this task can delete repository files created by ``subscription-manager``
    and other tools. But will raise ``ValueError`` if the repository name is
    ``redhat``.

    :raise: ``ValueError`` if repository name is 'redhat'.

    """
    for name in args:
        name = name.rstrip('.repo')
        if name == 'redhat':
            raise ValueError('This task will not delete redhat.repo file.')
        run('rm -f /etc/yum.repos.d/{0}.repo'.format(name), warn_only=True)


@_silencer
def enable_repos(*args, **kwargs):
    """Enable repos passed as ``args`` using ``subscription-manager repos
    --enable``.

    For example::

        enable_repos('repo1', 'repo2')

    Will run the command ``subscription-manager repos --enable "repo1" --enable
    "repo2"``.

    If the keyword argument ``silent`` is ``True`` then the stdout output will
    be hidden.

    """
    run('subscription-manager repos {0}'
        .format(' '.join(['--enable "{0}"'.format(repo) for repo in args])))


def create_custom_repos(**kwargs):
    """Create custom repofiles.

    Each ``kwargs`` item will result in one repository file created. Where the
    key is the repository filename and repository name, and the value is the
    repository URL.

    For example::

        create_custom_repo(custom_repo='http://repourl.domain.com/path')

    Will create a repository file named ``custom_repo.repo`` with the following
    contents::

        [custom_repo]
        name=custom_repo
        baseurl=http://repourl.domain.com/path
        enabled=1
        gpgcheck=0

    """
    for name, url in kwargs.items():
        repo_file = StringIO()
        repo_file.write(
            '[{name}]\n'
            'name={name}\n'
            'baseurl={url}\n'
            'enabled=1\n'
            'gpgcheck=0\n'
            .format(name=name, url=url)
        )
        put(local_path=repo_file,
            remote_path='/etc/yum.repos.d/{0}.repo'.format(name))
        repo_file.close()


def enable_satellite_repos(cdn=False, beta=False, disable_enabled=True,
                           cdn_version='6.1'):
    """Enable repositories required to install Satellite 6

    :param cdn: Indicates if the CDN Satellite 6 repo should be enabled or not
    :param beta: Indicates if the Beta Satellite 6 repo should be enabled or
        not. The Beta repo is available through the CDN and, if both ``cdn``
        and ``beta`` are ``True``, the beta repo will be used instead of the
        stable one.
    :param disable_enabled: If True, disable all repositories (including beaker
        repositories) before enabling repositories.
    :param version: Indicates which satellite version should be installed,
        default set to 6.1.

    """
    if isinstance(cdn, str):
        cdn = (cdn.lower() == 'true')
    if isinstance(beta, str):
        beta = (beta.lower() == 'true')
    if isinstance(disable_enabled, str):
        disable_enabled = (disable_enabled.lower() == 'true')

    if disable_enabled is True:
        disable_beaker_repos(silent=True)
        disable_repos('*', silent=True)

    repos = [
        'rhel-{0}-server-rpms',
        'rhel-server-rhscl-{0}-rpms',
    ]
    if beta is True:
        repos.append('rhel-server-{0}-satellite-6-beta-rpms')
    if cdn is True:
        if cdn_version == '6.0':
            repos.append('rhel-{0}-server-satellite-6.0-rpms')
        elif cdn_version == '6.1':
            repos.append('rhel-{0}-server-satellite-6.1-rpms')
        else:
            raise ValueError('CDN Version should be either 6.0 or 6.1')

    enable_repos(*[repo.format(distro_info()[1]) for repo in repos])
    run('yum repolist')


@_silencer
def disable_beaker_repos(**kwargs):
    """Disable beaker repositories

    If yum-config-manager is available this task will disable the repos, if not
    it will move the beaker repo files to the running user home directory

    If the keyword argument ``silent`` is ``True`` then the stdout output will
    be hidden.

    """
    # Clean up system if Beaker-based
    result = run('which yum-config-manager', quiet=True)
    if result.succeeded:
        run('yum-config-manager --disable "beaker*"')
    else:
        run('mv /etc/yum.repos.d/beaker-* ~/', warn_only=True)
    run('rm -rf /var/cache/yum*')


def manage_custom_repos(**kwargs):
    """Enable or disable custom repositories.

    The keyword key is the repository filename and the boolean value indicates
    if it should enable if ``True`` or disable if ``False``.

    """
    for name, enable in kwargs.items():
        repo_file = '/etc/yum.repos.d/{0}.repo'.format(name)
        run('sed -i -e "s/^enabled=.*/enabled={0}/" {1}'.format(
            1 if enable is True else 0,
            repo_file
        ))
