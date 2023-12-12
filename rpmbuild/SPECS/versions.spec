Name: versions
Version: 1.0.0
Release: 1%{?dist}
Summary: Easily manage versions of files

License: GNU GPL
URL: https://github.com/singaltanmay/versions
Source0: %{name}-%{version}.tar.gz

Requires: bash python3 git

%description
Easily manage versions of files

%prep
%setup -q

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/%{_bindir}
tree .
cp %{name}.py $RPM_BUILD_ROOT/%{_bindir}

%clean
rm -rf $RPM_BUILD_ROOT

%files
%{_bindir}/%{name}.py

%changelog
* Mon Dec 06 2021 Tanmay Singal <tanmaysingal@icloud.com>
- First version being packaged
