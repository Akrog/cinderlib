%{!?upstream_version: %global upstream_version %{version}%{?milestone}}

%global pypi_name cinderlib
%global common_summary Python library for direct usage of Cinder drivers without the services
%global common_desc \
The Cinder Library, also known as cinderlib, is a Python library that leverages \
the Cinder project to provide an object oriented abstraction around Cinder's \
storage drivers to allow their usage directly without running any of the Cinder \
services or surrounding services, such as KeyStone, MySQL or RabbitMQ. \
\
The library is intended for developers who only need the basic CRUD \
functionality of the drivers and don't care for all the additional features \
Cinder provides such as quotas, replication, multi-tenancy, migrations, \
retyping, scheduling, backups, authorization, authentication, REST API, etc.

Name:           %{pypi_name}
Version:        0.3.10
Release:        1%{?dist}
Summary:        %{common_summary}

License:        ASL 2.0
URL:            https://docs.openstack.org/cinderlib/latest/
Source0:        https://tarballs.openstack.org/%{pypi_name}/%{pypi_name}-%{upstream_version}.tar.gz
BuildArch:      noarch
%description
%{common_desc}

%package -n python2-%{pypi_name}
Summary:        %{common_summary}

Requires:       python-pbr
Requires:       openstack-cinder >= 12.0.0
Requires:       sudo

BuildRequires:  git
BuildRequires:  python2-devel
BuildRequires:  python-setuptools
BuildRequires:  python-pbr
BuildRequires:  openstack-cinder
# Required for unit tests
BuildRequires:    python-ddt
BuildRequires:    python2-os-testr
BuildRequires:    python2-oslotest

%description -n python2-%{pypi_name}
%{common_desc}

%if 0%{?with_python3}
%package -n python3-%{pypi_name}
Summary:        %{common_summary}

Requires:       python3-pbr
Requires:       openstack-cinder >= 12.0.0
Requires:       sudo

BuildRequires:  git
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pbr
BuildRequires:  openstack-cinder

%description -n python3-%{pypi_name}
%{common_desc}
%endif

%package doc
Summary:        Documentation for cinderlib

BuildRequires:  graphviz
BuildRequires:  python2-sphinx
BuildRequires:  python2-openstackdocstheme
BuildRequires:  python2-sphinxcontrib-apidoc

%description doc
This package contains the documentation files for %{pypi_name}.

%{common_desc}

%package tests-unit
Summary:        Cinderlib unit tests

Requires:    python-ddt
Requires:    python2-os-testr
Requires:    python2-oslotest

%description tests-unit
This package contains the unit tests for %{pypi_name}.

%{common_desc}

%package tests-functional
Summary:        Cinderlib unit tests

Requires:    python-ddt
Requires:    python2-os-testr
Requires:    python2-oslotest

%description tests-functional
This package contains the functional tests for %{pypi_name}.

%{common_desc}

%package tests
Summary:        All cinderlib tests

Requires: %{pypi_name}-tests-unit
Requires: %{pypi_name}-tests-functional

%description tests
Virtual package for all %{pypi_name} tests.

%prep
%autosetup -n %{pypi_name}-%{upstream_version} -S git

# Remove the requirements file so that pbr hooks don't add its requirements
rm -rf {test-,}requirements.txt

# Remove the devstack plugin, gate playbooks, and CI tools
rm -rf devstack playbooks tools

%build
%py2_build

%if 0%{?with_python3}
%py3_build
%endif

# generate html docs
sphinx-build -b html doc/source doc/build/html
# remove the sphinx-build leftovers
rm -rf doc/build/html/{.doctrees,.buildinfo,.placeholder,_sources}

%check
OS_TEST_PATH=./cinderlib/tests/unit ostestr -c 2

%install
%py2_install

%if 0%{?with_python3}
%py3_install
%endif

%files -n python2-%{pypi_name}
%license LICENSE
%{python2_sitelib}/cinderlib*
%exclude %{python2_sitelib}/%{pypi_name}/tests

%if 0%{?with_python3}
%files -n python3-%{pypi_name}
%license LICENSE
%{python3_sitelib}/cinderlib*
%exclude %{python3_sitelib}/%{pypi_name}/tests
%endif

%files doc
%license LICENSE
%doc doc/build/html

%files tests-unit
%license LICENSE
%{python2_sitelib}/%{pypi_name}/tests/unit/*

%files tests-functional
%license LICENSE
%{python2_sitelib}/%{pypi_name}/tests/functional/*

%files tests
%exclude /*

%changelog
* Thu Mar 21 2019 Gorka Eguileor <geguileo@redhat.com> - 0.3.10-1
- Initial package.
