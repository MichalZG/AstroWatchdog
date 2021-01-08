# AstroWatchdog
AstroWatchdog is software for real-time monitoring of astronomical observations.
Each new image obtained and saved by the camera software is automatically analyzed just after appearing.<br>
Main tasks:\
<ul>
<li> Displaying the last frame from the telescope main camera as a sky image </li>
<li> Displaying basic information about the last frame </li>
<li> Marking target on the sky image </li>
<li> Displaying time series with photometry values </li>
<li> Alerting about long brake in observations </li>
</ul>

The basic task of the AstroWatchdog is just showing images with the basic information on the website. However, if approximate telescope pointing 
coordinates are available, AstroWatchdog will make an attempt to solve images astrometrically. 
If the solution is correct, AstroWatchdog will use target coordinates from the image header to circle the target on the image and 
calculate the distance between the target and the image center.
Moreover, basic photometry will be taken from the target. Values like SNR, FLUX_MAX, BKG, and FWHM will be shown in the website diagrams.

If there is no possibility to obtain a telescope position from a telescope system, Astrowatchodog can use header keys (like target coordinates)
for astrometry solution. 
The coordinates have to be close to the real telescope position but there can be a (Bigger radius will significantly extend the execution time) \

AstroWatchdog consists of two base modules: \
<ul>
<li> Factory - module for monitoring the appearance of new files and analyzing them </li>
<li> Monitor - module for showing the results on the website </li>
</ul>
But there are additional modules used by AstroWatchdog:
<ul>
<li> [Nova](http://nova.astrometry.net/) - Astrometry.net software used by factory module for finding astrometric solutions </li>
<li> [SExtractor](https://www.astromatic.net/software/sextractor) - Astromatic software used by the factory for obtaining photometry results of frame sources </li>
<li> [Redis](https://redis.io/) - in-memory database, used to communicate between factory and monitor </li>
<li> [InfluxDB](https://www.influxdata.com/) - time-series database for storing frames data </li>
</ul>

Redis, Influx, and nova are controlled by [docker-compose](https://docs.docker.com/compose/). SExtractor is invoked as a standalone Docker container when needed.
Data synchronization between AstroWatchdog and telescope control-computer is done by a simple bash script controlled by Unix service manager.
